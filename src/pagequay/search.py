import asyncio
import hashlib
import json
import secrets
import time
from contextlib import suppress
from urllib.parse import parse_qs, parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from playwright.async_api import Error as PlaywrightError

from .auth import digest
from .errors import PQError
from .models import Navigate
from .search_options import TIME_FILTERS, ddg_region

TRACKING = {"gclid", "fbclid", "msclkid"}


def normalize_url(url):
    parsed = urlsplit(url)
    query = parse_qs(parsed.query)
    if parsed.hostname and parsed.hostname.endswith("duckduckgo.com") and "uddg" in query:
        url = query["uddg"][0]
    elif parsed.hostname and parsed.hostname.endswith("google.com") and parsed.path == "/url":
        url = (query.get("q") or query.get("url") or [url])[0]
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
        return None
    pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING
    ]
    return urlunsplit(
        (parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or "/", urlencode(pairs), "")
    )


class Adapter:
    def __init__(self, name, base):
        self.name, self.base = name, base

    def url(self, query, locale, *, region=None, time_range="any"):
        parameters = {"q": query}
        if self.name == "google":
            parameters.update(hl=locale.split("-")[0], gl=locale.split("-")[1].lower())
        elif self.name == "duckduckgo":
            parameters["kl"] = ddg_region(locale, region)
            parameters["df"] = TIME_FILTERS[time_range]
        # Brave: no claim of reliable locale support for undocumented controls.
        return self.base + "?" + urlencode(parameters)

    def parse(self, html, limit):
        soup = BeautifulSoup(html, "html.parser")
        if soup.select_one('[data-pq-challenge="true"]'):
            raise PQError("CHALLENGE_REQUIRED", "Search engine requests human intervention", 409)
        text = soup.get_text(" ", strip=True).lower()
        if any(marker in text for marker in ("too many requests", "rate limit exceeded")):
            raise PQError(
                "RATE_LIMITED",
                "Search engine reports throttling; its quota is unknown",
                429,
                details={
                    "scope": "upstream_engine",
                    "cause": "upstream_throttling",
                    "retry_after_seconds": None,
                    "retry_at": None,
                },
            )
        if self.name == "duckduckgo":
            containers = soup.select(".result")
            selectors = ("a.result__a", ".result__snippet")
        elif self.name == "brave":
            containers = soup.select(".snippet")
            selectors = ("a[href]:has(.title), a.title", ".snippet-description, .description")
        else:
            containers = soup.select(".MjjYud, .g")
            selectors = ("a:has(h3)", ".VwiC3b, .IsZvec")
        results = []
        for container in containers:
            classes = " ".join(container.get("class", []))
            if (
                container.select_one("[data-text-ad], .badge--ad, .ad-label")
                or "result--ad" in classes
            ):
                continue
            link = container.select_one(selectors[0])
            if not link:
                continue
            exact_url = unwrap_url(urljoin(self.base, link.get("href", "")))
            url = normalize_url(exact_url)
            if not url or urlsplit(url).hostname in {
                "duckduckgo.com",
                "search.brave.com",
                "www.google.com",
            }:
                continue
            title = link.get_text(" ", strip=True)
            if not title:
                continue
            snippet = container.select_one(selectors[1])
            results.append(
                {
                    "rank": len(results) + 1,
                    "title": title[:500],
                    "url": url,
                    "exact_url": exact_url,
                    "engine_rank": len(results) + 1,
                    "snippet": snippet.get_text(" ", strip=True)[:2000] if snippet else "",
                    "source_engines": [self.name],
                    "fetched_at": time.time(),
                    "result_type": "uncertain",
                }
            )
            if len(results) >= limit:
                break
        if not results and not any(
            marker in soup.get_text(" ", strip=True).lower()
            for marker in ("no results", "aucun résultat", "no more results")
        ):
            raise PQError("UPSTREAM_CHANGED", "Search HTML not recognized by adapter", 502)
        return results


ADAPTERS = {
    "duckduckgo": Adapter("duckduckgo", "https://html.duckduckgo.com/html/"),
    "brave": Adapter("brave", "https://search.brave.com/search"),
    "google": Adapter("google", "https://www.google.com/search"),
}


def merge_results(groups, limit):
    merged = {}
    for group in groups:
        for result in group:
            url = normalize_url(result["url"])
            if not url:
                continue
            if url not in merged:
                merged[url] = {
                    **result,
                    "url": url,
                    "source_engines": list(result["source_engines"]),
                }
            else:
                for engine in result["source_engines"]:
                    if engine not in merged[url]["source_engines"]:
                        merged[url]["source_engines"].append(engine)
    return [
        {**result, "rank": index + 1} for index, result in enumerate(list(merged.values())[:limit])
    ]


def unwrap_url(url):
    """Keep the target URL verbatim after unwrapping known engine redirect URLs."""
    parsed = urlsplit(url)
    query = parse_qs(parsed.query)
    if parsed.hostname in {"duckduckgo.com", "www.duckduckgo.com"} and "uddg" in query:
        return query["uddg"][0]
    if parsed.hostname in {"google.com", "www.google.com"} and parsed.path == "/url":
        return (query.get("q") or query.get("url") or [url])[0]
    return url


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def ddg_form_controls(form, controls):
    parsed = urlsplit(form["url"])
    pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key not in controls
    ]
    fields = [field for field in form["fields"] if field[0] not in controls]
    fields.extend([key, value] for key, value in controls.items())
    return {**form, "url": urlunsplit(parsed._replace(query=urlencode(pairs))), "fields": fields}


def ddg_continuation(html, source_url, query, *, region=None, time_range=None):
    """Only follow an actual Next form from the HTML engine, never invent offsets."""
    soup = BeautifulSoup(html, "html.parser")
    for form in soup.select("form"):
        submit = next(
            (
                el
                for el in form.select('input[type="submit"], button')
                if (el.get("value", "") or el.get_text(" ", strip=True)).strip().lower()
                in {"next", "next page", "suivant", "page suivante", "more results"}
            ),
            None,
        )
        if submit is None or submit.has_attr("disabled"):
            continue
        url = urljoin(source_url, form.get("action", ""))
        parsed = urlsplit(url)
        method = form.get("method", "get").lower()
        if (
            parsed.scheme != "https"
            or parsed.hostname not in {"html.duckduckgo.com", "duckduckgo.com"}
            or parsed.port not in {None, 443}
            or parsed.username
            or parsed.password
            or parsed.path not in {"/html/", "/html"}
            or parsed.fragment
            or method not in {"get", "post"}
        ):
            return None, None, "continuation_unusable"
        fields = [
            [el["name"], el.get("value", "")]
            for el in form.select("input[name]")
            if el.get("type", "text").lower() == "hidden" and not el.has_attr("disabled")
        ]
        if submit.get("name"):
            fields.append([submit["name"], submit.get("value", "")])
        # Reapply only search controls; offsets and native engine tokens stay unchanged.
        controls = {}
        if region is not None:
            controls["kl"] = region
        if time_range is not None:
            controls["df"] = TIME_FILTERS[time_range]
        if controls:
            filtered = ddg_form_controls({"url": url, "fields": fields}, controls)
            url, fields = filtered["url"], filtered["fields"]
        if (
            [value for name, value in fields if name == "q"] != [query]
            or len(fields) > 40
            or len(json.dumps(fields).encode()) > 16000
        ):
            return None, None, "continuation_unusable"
        return {"url": url, "method": method, "fields": fields}, True, None
    text = soup.get_text(" ", strip=True).lower()
    exhausted = any(
        marker in text
        for marker in ("no more results", "no results", "aucun résultat", "fin des résultats")
    )
    return (
        None,
        False if exhausted else None,
        "exhausted" if exhausted else "continuation_unavailable",
    )


class SearchService:
    def __init__(self, browser, auth, db):
        self.browser, self.auth, self.db = browser, auth, db

    def engine(self, project, request):
        return request.engine or self.db.policy(project).search_default_engine

    def validate_filters(self, project, request):
        if (request.region is not None or request.time_range != "any") and self.engine(
            project, request
        ) != "duckduckgo":
            raise PQError(
                "INVALID_INPUT", "Region and date filters require the DuckDuckGo engine", 422
            )

    def claim(self, project, request, job):
        self.validate_filters(project, request)
        if not request.cursor:
            return
        row = self.db.one(
            "SELECT * FROM search_cursors WHERE token_hash=?", (digest(request.cursor),)
        )
        if (
            row is None
            or row["project_id"] != project["id"]
            or row["query"] != request.query
            or row["engine"] != self.engine(project, request)
            or row["locale"] != request.locale
            or row["region"] != request.region
            or row["time_range"] != request.time_range
        ):
            raise PQError("INVALID_CURSOR", "Continuation does not match this search", 409)
        current = self.db.project(project["slug"])
        if row["expires_at"] <= time.time():
            raise PQError("CURSOR_EXPIRED", "Search continuation expired; start a new search", 410)
        if row["profile_reset"] != current["last_reset"]:
            raise PQError("INVALID_CURSOR", "Profile reset invalidated the continuation", 409)
        if row["claimed_job_id"]:
            raise PQError(
                "CURSOR_USED",
                "Continuation already belongs to an operation",
                409,
                details={"job_url": f"/v1/projects/{project['slug']}/jobs/{row['claimed_job_id']}"},
            )
        changed = self.db.conn.execute(
            "UPDATE search_cursors SET claimed_job_id=? "
            "WHERE token_hash=? AND claimed_job_id IS NULL",
            (job.id, digest(request.cursor)),
        ).rowcount
        if not changed:
            raise PQError("CURSOR_USED", "Continuation is already being used", 409)

    def save_cursor(self, project, request, state):
        count = self.db.one(
            "SELECT COUNT(*) AS n FROM search_cursors WHERE project_id=? AND expires_at>? "
            "AND state<>'{}' AND token_hash<>?",
            (project["id"], time.time(), digest(request.cursor or "")),
        )["n"]
        if count >= self.db.policy(project).search_max_cursors_per_project:
            return None
        token = secrets.token_urlsafe(32)
        self.db.execute(
            "INSERT INTO search_cursors "
            "(token_hash,project_id,query,engine,locale,expires_at,profile_reset,state,"
            "region,time_range,claimed_job_id) VALUES (?,?,?,?,?,?,?,?,?,?,NULL)",
            (
                digest(token),
                project["id"],
                request.query,
                "duckduckgo",
                request.locale,
                state["expires_at"],
                self.db.project(project["slug"])["last_reset"],
                json.dumps(state),
                request.region,
                request.time_range,
            ),
        )
        return token

    def metadata(
        self,
        project,
        request,
        results,
        *,
        engine,
        engines_used,
        failures=None,
        state=None,
        next_cursor=None,
        has_more=None,
        stop_reason=None,
        partial=False,
    ):
        return {
            "project": project["slug"],
            "query": request.query,
            "locale": request.locale,
            "region": request.region,
            "time_range": request.time_range,
            "results": results,
            "engine_errors": failures or [],
            "engine": engine,
            "engines_used": engines_used,
            "requested_count": request.limit,
            "effective_limit": min(request.limit, self.db.policy(project).search_max_results),
            "returned_count": len(results),
            "next_cursor": next_cursor,
            "has_more": has_more,
            "stop_reason": stop_reason,
            "partial": partial,
            "pages_fetched": state["pages"] if state else 0,
            "duplicates_discarded": state["duplicates"] if state else 0,
            "cursor_expires_at": state["expires_at"] if next_cursor else None,
        }

    async def read_page(self, project, request, job, name, tab, form=None):
        self.auth.rate("search:" + project["id"] + ":" + name, 6, scope="project_engine")
        self.browser.events.emit(
            project,
            "job.progress",
            job_id=job.id,
            engine=name,
            scope=job.scope,
            phase="fetching_search_page",
        )
        if form:
            # Also covers continuations stored before the filter migration.
            form = ddg_form_controls(
                form,
                {
                    "kl": ddg_region(request.locale, request.region),
                    "df": TIME_FILTERS[request.time_range],
                },
            )
            await self.browser.submit_search_form(project, tab.id, form, job)
        else:
            await self.browser.navigate(
                project,
                Navigate(
                    url=ADAPTERS[name].url(
                        request.query,
                        request.locale,
                        region=request.region,
                        time_range=request.time_range,
                    )
                ),
                job,
                tab.id,
            )
        async with tab.lock:
            html = await tab.page.content()
        if len(html.encode()) > self.browser.settings.max_content_bytes:
            raise PQError("INVALID_INPUT", "Search response too large", 413)
        return html

    async def duckduckgo(self, project, request, job, state, tab):
        policy = self.db.policy(project)
        if not state:
            state = {
                "pending": [],
                "next_form": None,
                "seen": [],
                "page_signatures": [],
                "form_signatures": [],
                "pages": 0,
                "delivered": 0,
                "duplicates": 0,
                "expires_at": time.time() + policy.search_cursor_ttl_minutes * 60,
                "has_more": None,
                "stop_reason": None,
            }
        remaining = policy.search_max_total_results - state["delivered"]
        if remaining <= 0:
            return self.metadata(
                project,
                request,
                [],
                engine="duckduckgo",
                engines_used=["duckduckgo"],
                state=state,
                has_more=False,
                stop_reason="total_results_limit",
                partial=True,
            )
        if state["pages"] >= policy.search_max_pages and state["next_form"]:
            state.update(next_form=None, has_more=False, stop_reason="page_limit")
        if not state["pending"]:
            if state["pages"] >= policy.search_max_pages:
                return self.metadata(
                    project,
                    request,
                    [],
                    engine="duckduckgo",
                    engines_used=["duckduckgo"],
                    state=state,
                    has_more=False,
                    stop_reason="page_limit",
                )
            html = await self.read_page(
                project, request, job, "duckduckgo", tab, state["next_form"]
            )
            results = ADAPTERS["duckduckgo"].parse(html, 200)
            signature = fingerprint([row["url"] for row in results])
            state["pages"] += 1
            next_form, more, reason = ddg_continuation(
                html,
                tab.page.url,
                request.query,
                region=ddg_region(request.locale, request.region),
                time_range=request.time_range,
            )
            seen = set(state["seen"])
            fresh = []
            for row in results:
                if row["url"] in seen:
                    state["duplicates"] += 1
                    continue
                if len(seen) >= policy.search_max_total_results:
                    more, reason, next_form = False, "total_results_limit", None
                    break
                seen.add(row["url"])
                fresh.append(
                    {
                        **row,
                        "rank": len(state["seen"]) + len(fresh) + 1,
                        "page_number": state["pages"],
                    }
                )
            if signature in state["page_signatures"] or (results and not fresh):
                more, reason, next_form = False, "repeated_page", None
            if not results and next_form:
                more, reason, next_form = False, "no_progress", None
            state["page_signatures"].append(signature)
            if next_form:
                form_signature = fingerprint(next_form)
                if form_signature in state["form_signatures"]:
                    more, reason, next_form = False, "repeated_continuation", None
                else:
                    state["form_signatures"].append(form_signature)
            if state["pages"] >= policy.search_max_pages and next_form:
                more, reason, next_form = False, "page_limit", None
            if len(seen) >= policy.search_max_total_results and next_form:
                more, reason, next_form = False, "total_results_limit", None
            state.update(
                pending=fresh,
                next_form=next_form,
                seen=list(seen),
                has_more=more,
                stop_reason=reason,
            )
        limit = min(request.limit, policy.search_max_results, remaining)
        results, state["pending"] = state["pending"][:limit], state["pending"][limit:]
        state["delivered"] += len(results)
        if state["delivered"] >= policy.search_max_total_results:
            state.update(
                pending=[], next_form=None, has_more=False, stop_reason="total_results_limit"
            )
        cursor = None
        more, reason = state["has_more"], state["stop_reason"]
        if state["pending"] or state["next_form"]:
            if state["expires_at"] > time.time():
                cursor = self.save_cursor(project, request, state)
                if cursor:
                    more = True
                    reason = "result_limit" if state["pending"] else "page_complete"
                else:
                    more, reason = False, "cursor_capacity"
            else:
                more, reason = False, "cursor_expired"
        return self.metadata(
            project,
            request,
            results,
            engine="duckduckgo",
            engines_used=["duckduckgo"],
            state=state,
            next_cursor=cursor,
            has_more=more,
            stop_reason=reason,
            partial=reason
            in {
                "page_limit",
                "total_results_limit",
                "cursor_expired",
                "repeated_page",
                "repeated_continuation",
                "cursor_capacity",
                "no_progress",
            },
        )

    async def search(self, project, request, job):
        self.validate_filters(project, request)
        engine = self.engine(project, request)
        policy = self.db.policy(project)
        tab, committed, state = None, False, None
        output_cursor = None
        initial = self.metadata(project, request, [], engine=engine, engines_used=[])
        job.progress(initial)
        try:
            if request.cursor:
                row = self.db.one(
                    "SELECT * FROM search_cursors WHERE token_hash=?", (digest(request.cursor),)
                )
                if not row or row["claimed_job_id"] != job.id:
                    raise PQError(
                        "INVALID_CURSOR", "Continuation was not reserved by this job", 409
                    )
                if (
                    row["engine"] != engine
                    or row["query"] != request.query
                    or row["locale"] != request.locale
                    or row["region"] != request.region
                    or row["time_range"] != request.time_range
                    or row["profile_reset"] != self.db.project(project["slug"])["last_reset"]
                ):
                    raise PQError("INVALID_CURSOR", "Search binding changed while queued", 409)
                if row["expires_at"] <= time.time():
                    raise PQError("CURSOR_EXPIRED", "Continuation expired while queued", 410)
                state = json.loads(row["state"])
            job.check_authorization()
            # Each search owns one internal tab; never reuse a tab from another operation.
            if not state or not state["pending"]:
                allocation = asyncio.create_task(self.browser.new_tab(project))
                try:
                    tab = await asyncio.shield(allocation)
                except asyncio.CancelledError:
                    # Let the bounded browser allocation settle so its page cannot be orphaned.
                    with suppress(PQError, PlaywrightError):
                        allocated = await allocation
                        await self.browser.close_tab(project, allocated.id)
                    raise
                job.set_tab(tab.id)
            async with asyncio.timeout(
                self.browser.settings.job_timeout_seconds
                + self.browser.settings.human_timeout_seconds
            ):
                if engine == "duckduckgo":
                    result = await self.duckduckgo(project, request, job, state, tab)
                else:
                    strategy = request.strategy or policy.search_auto_strategy
                    names = ["duckduckgo", "brave", "google"] if engine == "auto" else [engine]
                    groups, failures, used = [], [], []
                    for name in names:
                        job.check_authorization()
                        try:
                            html = await self.read_page(project, request, job, name, tab)
                            group = ADAPTERS[name].parse(
                                html, min(request.limit, policy.search_max_results)
                            )
                            groups.append(group)
                            used.append(name)
                            result = self.metadata(
                                project,
                                request,
                                merge_results(
                                    groups, min(request.limit, policy.search_max_results)
                                ),
                                engine=used[0] if len(used) == 1 else "mixed",
                                engines_used=used,
                                failures=failures,
                                partial=bool(failures),
                            )
                            job.progress(result)
                            if strategy == "fallback" and group:
                                break
                        except PQError as exc:
                            if exc.code == "RATE_LIMITED":
                                exc.details = {**(exc.details or {}), "engine": name}
                            failures.append(
                                {"engine": name, "code": exc.code, "details": exc.details}
                            )
                            if job.partial_result:
                                job.partial_result["engine_errors"] = list(failures)
                            if engine != "auto" or exc.code in {
                                "CHALLENGE_REQUIRED",
                                "FORBIDDEN",
                                "UNAUTHORIZED",
                                "RATE_LIMITED",
                            }:
                                raise
                    if not groups:
                        raise PQError("UPSTREAM_UNAVAILABLE", "All requested engines failed", 502)
                    result = self.metadata(
                        project,
                        request,
                        merge_results(groups, min(request.limit, policy.search_max_results)),
                        engine=used[0] if len(used) == 1 else "mixed",
                        engines_used=used,
                        failures=failures,
                        stop_reason="pagination_not_supported",
                        partial=bool(failures),
                    )
            output_cursor = result.get("next_cursor")
            job.check_authorization()
            committed = True
            return result
        except PQError as exc:
            if exc.code == "RATE_LIMITED":
                exc.details = {
                    "scope": "upstream_engine",
                    "cause": "unknown",
                    "retry_after_seconds": None,
                    "retry_at": None,
                    **(exc.details or {}),
                    "engine": (exc.details or {}).get("engine", engine),
                    "can_resume_continuation": bool(
                        request.cursor and state and state["expires_at"] > time.time()
                    ),
                    "resume_cursor": request.cursor
                    if state and state["expires_at"] > time.time()
                    else None,
                    "partial_results": (job.partial_result or {}).get("results", []),
                }
            if job.partial_result:
                job.partial_result["partial"] = True
                job.partial_result["stop_reason"] = exc.code.lower()
            raise
        finally:
            if request.cursor and not committed:
                self.db.execute(
                    "UPDATE search_cursors SET claimed_job_id=NULL "
                    "WHERE token_hash=? AND claimed_job_id=?",
                    (digest(request.cursor), job.id),
                )
            if output_cursor and not committed:
                self.db.execute(
                    "DELETE FROM search_cursors WHERE token_hash=?", (digest(output_cursor),)
                )
            if tab is not None:
                with suppress(PQError, PlaywrightError):
                    await self.browser.close_tab(project, tab.id)
