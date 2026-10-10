import time
from urllib.parse import parse_qs, parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from .errors import PQError
from .models import Navigate

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

    def url(self, query, locale):
        parameters = {"q": query}
        if self.name == "google":
            parameters.update(hl=locale.split("-")[0], gl=locale.split("-")[1].lower())
        # Other engines: no claim of reliable locale support for undocumented controls.
        return self.base + "?" + urlencode(parameters)

    def parse(self, html, limit):
        soup = BeautifulSoup(html, "html.parser")
        if soup.select_one('[data-pq-challenge="true"]'):
            raise PQError("CHALLENGE_REQUIRED", "Search engine requests human intervention", 409)
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
            url = normalize_url(urljoin(self.base, link.get("href", "")))
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


class SearchService:
    def __init__(self, browser, auth, db):
        self.browser, self.auth, self.db = browser, auth, db

    async def search(self, project, request, job):
        policy = self.db.policy(project)
        engine = request.engine or policy.search_default_engine
        strategy = request.strategy or policy.search_auto_strategy
        limit = min(request.limit, policy.search_max_results)
        engines = ["duckduckgo", "brave", "google"] if engine == "auto" else [engine]
        groups, failures, tab_id = [], [], None
        for name in engines:
            job.check_authorization()
            self.auth.rate("search:" + project["id"] + ":" + name, 6)
            adapter = ADAPTERS[name]
            self.browser.events.emit(
                project, "job.progress", job_id=job.id, engine=name, scope=job.scope
            )
            try:
                result = await self.browser.navigate(
                    project, Navigate(url=adapter.url(request.query, request.locale)), job, tab_id
                )
                tab_id = result["tab_id"]
                tab = self.browser.tab(project, tab_id)
                async with tab.lock:
                    html = await tab.page.content()
                if len(html.encode()) > self.browser.settings.max_content_bytes:
                    raise PQError("INVALID_INPUT", "Search response too large", 413)
                groups.append(adapter.parse(html, limit))
                if strategy == "fallback" and groups[-1]:
                    break
            except PQError as exc:
                failures.append({"engine": name, "code": exc.code})
                tab_id = job.tab_id
                if engine != "auto" or exc.code in {
                    "CHALLENGE_REQUIRED",
                    "FORBIDDEN",
                    "UNAUTHORIZED",
                }:
                    raise
        if not groups:
            raise PQError("UPSTREAM_UNAVAILABLE", "All requested search engines failed", 502)
        results = merge_results(groups, limit)
        if tab_id:
            await self.browser.close_tab(project, tab_id)
        return {
            "project": project["slug"],
            "query": request.query,
            "results": results,
            "engine_errors": failures,
        }
