import asyncio
import json
import time
from html import escape
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from pagequay.auth import digest
from pagequay.errors import PQError
from pagequay.jobs import Jobs
from pagequay.models import Search
from pagequay.search import ADAPTERS, ddg_continuation
from pagequay.storage import uid


def html_page(numbers, *, next_offset=None, query="robot agriculture", no_more=False):
    html = "".join(
        f'<div class="result"><a class="result__a" '
        f'href="https://example.org/{n}?utm_source=ddg&amp;x=%2f#section">Site {n}</a>'
        f'<span class="result__snippet">Description {n}</span></div>'
        for n in numbers
    )
    if next_offset is not None:
        html += (
            f'<div class="nav-link"><form action="/html/" method="post">'
            f'<input type="hidden" name="q" value="{escape(query, quote=True)}">'
            f'<input type="hidden" name="s" value="{next_offset}">'
            '<input type="hidden" name="vqd" value="engine-issued-token">'
            '<input type="submit" value="Next"></form></div>'
        )
    if no_more:
        html += "<p>No more results</p>"
    return html


class FakeBrowser:
    def __init__(self, rt):
        self.settings, self.events = rt.settings, rt.events
        self.tabs, self.pages, self.calls, self.closed = {}, [], [], []
        self.gate = None
        self.challenge = False

    async def new_tab(self, project):
        tab = SimpleNamespace(id=uid(), lock=asyncio.Lock(), page=SimpleNamespace())
        tab.page.url = "about:blank"
        tab.page.html = ""

        async def content():
            return tab.page.html

        tab.page.content = content
        self.tabs[tab.id] = tab
        return tab

    async def navigate(self, project, request, job, tab_id):
        self.calls.append(("get", request.url))
        await self.fetch(job, self.tabs[tab_id], request.url)
        return {"tab_id": tab_id}

    async def submit_search_form(self, project, tab_id, form, job):
        self.calls.append(("form", form))
        await self.fetch(job, self.tabs[tab_id], form["url"])

    async def fetch(self, job, tab, url):
        if self.gate is not None:
            await self.gate.wait()
        if self.challenge:
            await job.wait_for_human(tab.id, None)
        page = self.pages.pop(0)
        if isinstance(page, Exception):
            raise page
        tab.page.html, tab.page.url = page, url

    async def close_tab(self, project, tab_id):
        self.closed.append(tab_id)
        self.tabs.pop(tab_id)


@pytest.fixture
async def search_client(app, monkeypatch):
    async def bounded_read(page, kind, max_bytes):
        assert kind == "html"
        if len(page.html.encode()) > max_bytes:
            raise PQError("INVALID_INPUT", "Search response too large", 413)
        return page.html

    monkeypatch.setattr("pagequay.search.read_page", bounded_read)
    async with app.router.lifespan_context(app):
        rt = app.state.rt
        project = rt.db.create_project("universrobot", "UniversRobot")
        other = rt.db.create_project("other-project", "Other")
        key_id, token = rt.auth.create_key(project, "Test", ["search:read"], rate_limit=600)
        _, other_token = rt.auth.create_key(other, "Other", ["search:read"], rate_limit=600)
        fake = FakeBrowser(rt)
        rt.search.browser = fake
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 1234)),
            base_url="http://testserver",
            headers={"Authorization": "Bearer " + token},
        ) as client:
            yield client, rt, fake, project, key_id, other_token, token


async def complete(client, payload, *, headers=None):
    response = await client.post("/v1/projects/universrobot/search", json=payload, headers=headers)
    assert response.status_code == 202, response.text
    value = response.json()
    for _ in range(400):
        job = (await client.get(value["url"])).json()
        if job["status"] not in {"queued", "running"}:
            return job
        await asyncio.sleep(0.005)
    pytest.fail("Simulated search did not finish")


async def test_three_progressive_pages_and_exact_urls(search_client):
    client, rt, fake, _, _, _, token = search_client
    fake.pages = [
        html_page([1, 2], next_offset=2),
        html_page([2, 3, 4], next_offset=4),
        html_page([5, 6], no_more=True),
    ]
    payload = {"query": "robot agriculture", "engine": "duckduckgo", "limit": 10}
    all_results = []
    for page in range(1, 4):
        row = await complete(client, payload)
        assert row["status"] == "completed", row
        result = row["result"]
        all_results.extend(result["results"])
        assert result["pages_fetched"] == page
        assert result["requested_count"] == 10
        assert result["returned_count"] == len(result["results"])
        assert result["engine"] == "duckduckgo"
        assert result["engines_used"] == ["duckduckgo"]
        assert bool(result["next_cursor"]) == (page < 3)
        if page < 3:
            payload["cursor"] = result["next_cursor"]
    assert [r["rank"] for r in all_results] == [1, 2, 3, 4, 5, 6]
    assert all(r["exact_url"].endswith("?utm_source=ddg&x=%2f#section") for r in all_results)
    assert all(r["source_engines"] == ["duckduckgo"] for r in all_results)
    assert result["duplicates_discarded"] == 1
    assert result["has_more"] is False and result["stop_reason"] == "exhausted"
    assert not fake.tabs and len(fake.closed) == 3
    assert [call[0] for call in fake.calls] == ["get", "form", "form"]
    assert fake.calls[1][1]["fields"] == [
        ["q", payload["query"]],
        ["s", "2"],
        ["vqd", "engine-issued-token"],
        ["kl", "fr-fr"],
        ["df", ""],
    ]
    assert token not in json.dumps(result) and token not in json.dumps(fake.calls)
    assert token not in "\n".join(r["state"] for r in rt.db.all("SELECT state FROM search_cursors"))


@pytest.mark.parametrize(
    "query,locale",
    [
        ('robots agricoles "France"', "fr-FR"),
        ("robotics farming -jobs", "en-US"),
        ("żniwa robot", "pl-PL"),
    ],
)
async def test_keywords_locales_and_legacy_limit_cap(search_client, query, locale):
    client, _, fake, *_ = search_client
    fake.pages = [html_page(range(25), query=query)]
    row = await complete(
        client, {"query": query, "locale": locale, "engine": "duckduckgo", "limit": 50}
    )
    result = row["result"]
    assert result["requested_count"] == 50 and result["effective_limit"] == 10
    assert result["returned_count"] == 10 and result["next_cursor"]
    params = parse_qs(urlsplit(fake.calls[0][1]).query)
    assert params["q"] == [query] and params["kl"] == [locale[3:].lower() + "-" + locale[:2]]
    # Cached remainder is returned without spending another engine attempt or creating a tab.
    row = await complete(
        client,
        {
            "query": query,
            "locale": locale,
            "engine": "duckduckgo",
            "limit": 5,
            "cursor": result["next_cursor"],
        },
    )
    assert row["result"]["returned_count"] == 5
    assert [r["rank"] for r in row["result"]["results"]] == [11, 12, 13, 14, 15]
    assert len(fake.calls) == 1 and len(fake.closed) == 1


@pytest.mark.parametrize(
    "region,period,code",
    [
        ("fr-fr", "day", "d"),
        ("pl-pl", "week", "w"),
        ("us-en", "month", "m"),
        ("uk-en", "year", "y"),
        ("wt-wt", "any", ""),
    ],
)
async def test_region_period_survive_remainder_and_native_pagination(
    search_client, region, period, code
):
    client, rt, fake, *_ = search_client
    fake.pages = [html_page([1, 2], next_offset=2), html_page([3], no_more=True)]
    payload = {
        "query": "robot agriculture",
        "engine": "duckduckgo",
        "locale": "fr-FR",
        "region": region,
        "time_range": period,
        "limit": 1,
    }
    first = (await complete(client, payload))["result"]
    assert first["region"] == region and first["time_range"] == period
    params = parse_qs(urlsplit(fake.calls[0][1]).query, keep_blank_values=True)
    assert params["kl"] == [region] and params["df"] == [code]
    for changed in ({"region": "ca-fr"}, {"time_range": "week" if period != "week" else "day"}):
        response = await client.post(
            "/v1/projects/universrobot/search",
            json={**payload, "cursor": first["next_cursor"], **changed},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "INVALID_CURSOR"
    second = (await complete(client, {**payload, "cursor": first["next_cursor"]}))["result"]
    assert len(fake.calls) == 1  # Stored remainder still carries the filter binding.
    third = (await complete(client, {**payload, "cursor": second["next_cursor"]}))["result"]
    assert third["region"] == region and third["time_range"] == period
    form = fake.calls[1][1]
    assert [value for name, value in form["fields"] if name == "kl"] == [region]
    assert [value for name, value in form["fields"] if name == "df"] == [code]
    assert [value for name, value in form["fields"] if name == "vqd"] == ["engine-issued-token"]
    assert third["has_more"] is False and not fake.tabs
    # Binding survives state cleanup: reusing a consumed filtered cursor reports CURSOR_USED.
    response = await client.post(
        "/v1/projects/universrobot/search", json={**payload, "cursor": second["next_cursor"]}
    )
    assert response.json()["error"]["code"] == "CURSOR_USED"
    assert (
        rt.db.one(
            "SELECT state FROM search_cursors WHERE token_hash=?", (digest(second["next_cursor"]),)
        )["state"]
        == "{}"
    )


@pytest.mark.parametrize(
    "extra",
    [
        {"region": "fr-FR"},
        {"region": "zz-zz"},
        {"time_range": "past_week"},
        {"engine": "google", "time_range": "day"},
        {"engine": "brave", "region": "pl-pl"},
        {"engine": "auto", "time_range": "week"},
    ],
)
async def test_invalid_or_unsupported_filters_rejected_before_admission(search_client, extra):
    client, rt, fake, *_ = search_client
    response = await client.post(
        "/v1/projects/universrobot/search",
        json={"query": "robot agriculture", "engine": "duckduckgo", **extra},
    )
    assert response.status_code == 422
    assert not fake.calls and not rt.db.all("SELECT * FROM jobs")


async def test_project_default_engine_must_support_filters(search_client):
    client, rt, fake, project, *_ = search_client
    rt.db.execute(
        "UPDATE projects SET config=? WHERE id=?",
        (json.dumps({"search_default_engine": "google"}), project["id"]),
    )
    response = await client.post(
        "/v1/projects/universrobot/search", json={"query": "robot", "time_range": "week"}
    )
    assert response.status_code == 422 and not fake.calls


async def test_filters_participate_in_idempotency_and_defaults_replay(search_client):
    client, _, fake, *_ = search_client
    fake.pages = [html_page([1])]
    payload = {"query": "robot agriculture", "engine": "duckduckgo"}
    headers = {"Idempotency-Key": "filter-binding"}
    first = await complete(client, payload, headers=headers)
    same = await complete(client, {**payload, "region": None, "time_range": "any"}, headers=headers)
    assert first["id"] == same["id"] and len(fake.calls) == 1
    for filters in ({"time_range": "week"}, {"region": "pl-pl"}):
        response = await client.post(
            "/v1/projects/universrobot/search", json={**payload, **filters}, headers=headers
        )
        assert response.status_code == 409 and response.json()["error"]["code"] == "CONFLICT"


def test_continuation_overrides_stale_filters_without_changing_native_tokens():
    html = (
        html_page([1], next_offset=2)
        .replace('action="/html/"', 'action="/html/?kl=us-en&amp;df=y"')
        .replace(
            '<input type="submit"',
            '<input type="hidden" name="kl" value="us-en">'
            '<input type="hidden" name="df" value="y"><input type="submit"',
        )
    )
    form, more, reason = ddg_continuation(
        html, ADAPTERS["duckduckgo"].base, "robot agriculture", region="pl-pl", time_range="any"
    )
    assert more and reason is None and not urlsplit(form["url"]).query
    assert dict(form["fields"]) == {
        "q": "robot agriculture",
        "s": "2",
        "vqd": "engine-issued-token",
        "kl": "pl-pl",
        "df": "",
    }


def test_filter_migration_preserves_existing_cursor(tmp_path):
    from pagequay.storage import Storage

    db = Storage(tmp_path)
    project = db.create_project("legacy", "Legacy")
    # Reproduce the preceding schema with a pending native continuation.
    db.execute("ALTER TABLE search_cursors DROP COLUMN region")
    db.execute("ALTER TABLE search_cursors DROP COLUMN time_range")
    db.execute("DELETE FROM schema_migrations WHERE version='004_search_filters.sql'")
    state = json.dumps({"next_form": {"url": "https://html.duckduckgo.com/html/", "fields": []}})
    db.execute(
        "INSERT INTO search_cursors VALUES (?,?,?,?,?,?,?,?,NULL)",
        (
            "legacy-token-hash",
            project["id"],
            "robot",
            "duckduckgo",
            "fr-FR",
            time.time() + 900,
            project["last_reset"],
            state,
        ),
    )
    db.close()
    db = Storage(tmp_path)
    try:
        row = db.one("SELECT * FROM search_cursors WHERE token_hash='legacy-token-hash'")
        assert row["region"] is None and row["time_range"] == "any"
        assert row["state"] == state and row["locale"] == "fr-FR"
    finally:
        db.close()


@pytest.mark.parametrize(
    "second,reason",
    [
        (html_page([1], next_offset=2), "repeated_page"),
        (html_page([2], next_offset=1), "repeated_continuation"),
        (html_page([], no_more=True), "exhausted"),
        (html_page([2]), "continuation_unavailable"),
    ],
)
async def test_repetition_and_unknown_end(search_client, second, reason):
    client, _, fake, *_ = search_client
    fake.pages = [html_page([1], next_offset=1), second]
    payload = {"query": "robot agriculture", "engine": "duckduckgo"}
    first = (await complete(client, payload))["result"]
    row = await complete(client, {**payload, "cursor": first["next_cursor"]})
    result = row["result"]
    assert result["next_cursor"] is None and result["stop_reason"] == reason
    assert result["has_more"] is (None if reason == "continuation_unavailable" else False)
    if reason == "repeated_page":
        assert result["results"] == []
    assert not fake.tabs


async def test_cursor_binding_replay_expiry_reset_and_rollback(search_client):
    client, rt, fake, project, _, other_token, _ = search_client
    fake.pages = [html_page([1, 2, 3], next_offset=3)]
    payload = {"query": "robot agriculture", "engine": "duckduckgo", "limit": 1}
    cursor = (await complete(client, payload))["result"]["next_cursor"]
    before = rt.db.one("SELECT COUNT(*) AS n FROM jobs")["n"]
    for extra in (
        {"query": "different"},
        {"locale": "en-US"},
        {"engine": "brave"},
        {"engine": "auto"},
    ):
        response = await client.post(
            "/v1/projects/universrobot/search", json={**payload, "cursor": cursor, **extra}
        )
        assert response.status_code == 409 and response.json()["error"]["code"] == "INVALID_CURSOR"
    response = await client.post(
        "/v1/projects/other-project/search",
        json={**payload, "cursor": cursor},
        headers={"Authorization": "Bearer " + other_token},
    )
    assert response.status_code == 409
    assert rt.db.one("SELECT COUNT(*) AS n FROM jobs")["n"] == before
    rt.db.execute("UPDATE search_cursors SET expires_at=0 WHERE token_hash=?", (digest(cursor),))
    response = await client.post(
        "/v1/projects/universrobot/search", json={**payload, "cursor": cursor}
    )
    assert response.status_code == 410 and response.json()["error"]["code"] == "CURSOR_EXPIRED"
    rt.db.execute("UPDATE search_cursors SET expires_at=?", (time.time() + 100,))
    rt.db.execute("UPDATE projects SET last_reset=last_reset+1 WHERE id=?", (project["id"],))
    response = await client.post(
        "/v1/projects/universrobot/search", json={**payload, "cursor": cursor}
    )
    assert response.status_code == 409
    assert rt.db.one("SELECT COUNT(*) AS n FROM jobs")["n"] == before


async def test_idempotency_concurrency_payload_conflict_cursor_and_restart(search_client):
    client, rt, fake, project, key_id, *_ = search_client
    fake.pages = [html_page([1, 2, 3], next_offset=3)]
    fake.gate = asyncio.Event()
    payload = {"query": "robot agriculture", "engine": "duckduckgo", "limit": 1}
    responses = await asyncio.gather(
        *(
            client.post(
                "/v1/projects/universrobot/search",
                json=payload,
                headers={"Idempotency-Key": "same-request"},
            )
            for _ in range(12)
        )
    )
    assert all(r.status_code == 202 for r in responses)
    ids = {r.json()["job_id"] for r in responses}
    assert len(ids) == 1
    response = await client.post(
        "/v1/projects/universrobot/search",
        json={**payload, "query": "other"},
        headers={"Idempotency-Key": "same-request"},
    )
    assert response.status_code == 409
    fake.gate.set()
    await rt.jobs.active[ids.pop()].task
    first = await complete(client, payload, headers={"Idempotency-Key": "same-request"})
    cursor = first["result"]["next_cursor"]
    second = await complete(
        client, {**payload, "cursor": cursor}, headers={"Idempotency-Key": "slice2"}
    )
    response = await client.post(
        "/v1/projects/universrobot/search", json={**payload, "cursor": cursor}
    )
    assert response.status_code == 409 and response.json()["error"]["code"] == "CURSOR_USED"
    replay = await client.post(
        "/v1/projects/universrobot/search",
        json={**payload, "cursor": cursor},
        headers={"Idempotency-Key": "slice2"},
    )
    assert replay.json()["job_id"] == second["id"] and replay.json()["idempotency_replayed"]
    restarted = Jobs(rt.db, rt.settings, rt.auth, rt.events)
    rt.jobs = restarted
    rt.browser.busy = restarted.busy
    replay = await complete(client, payload, headers={"Idempotency-Key": "same-request"})
    assert replay["id"] == first["id"] and len(fake.calls) == 1
    # A failed interrupted operation releases its cursor reservation on restart.
    candidate = second["result"]["next_cursor"]
    rt.db.execute(
        "UPDATE search_cursors SET claimed_job_id=? WHERE token_hash=?",
        (first["id"], digest(candidate)),
    )
    rt.db.execute("UPDATE jobs SET status='running' WHERE id=?", (first["id"],))
    restarted = Jobs(rt.db, rt.settings, rt.auth, rt.events)
    assert (
        rt.db.one(
            "SELECT claimed_job_id FROM search_cursors WHERE token_hash=?", (digest(candidate),)
        )["claimed_job_id"]
        is None
    )
    assert restarted.get(project, first["id"])["status"] == "failed"
    # Idempotency expires after 24 hours; another operation can then be created.
    rt.db.execute("UPDATE search_idempotency SET expires_at=0")
    fake.pages = [html_page([9])]
    again = await complete(client, payload, headers={"Idempotency-Key": "same-request"})
    assert again["id"] != first["id"]
    assert key_id == rt.db.one("SELECT key_id FROM jobs WHERE id=?", (again["id"],))["key_id"]


async def test_engine_quota_failure_and_resumable_cursor(search_client):
    client, rt, fake, project, *_ = search_client
    fake.pages = [html_page([1], next_offset=1)]
    payload = {"query": "robot agriculture", "engine": "duckduckgo"}
    cursor = (await complete(client, payload))["result"]["next_cursor"]
    bucket = "search:" + project["id"] + ":duckduckgo"
    rt.db.execute("UPDATE limits SET count=6 WHERE bucket=?", (bucket,))
    row = await complete(client, {**payload, "cursor": cursor})
    assert row["status"] == "failed" and row["error"]["code"] == "RATE_LIMITED"
    details = row["error"]["details"]
    assert details["scope"] == "project_engine" and details["cause"] == "pagequay_quota"
    assert details["limit"] == 6 and details["window_seconds"] == 60
    assert 1 <= details["retry_after_seconds"] <= 60 and details["retry_at"] > time.time()
    assert details["can_resume_continuation"] and details["resume_cursor"] == cursor
    assert details["partial_results"] == [] and not fake.tabs
    rt.db.execute("UPDATE limits SET window=window-61 WHERE bucket=?", (bucket,))
    fake.pages = [html_page([2], no_more=True)]
    row = await complete(client, {**payload, "cursor": cursor})
    assert row["status"] == "completed" and row["result"]["results"][0]["rank"] == 2


async def test_http_quota_retry_after_and_partial_engine_provenance(search_client):
    client, rt, fake, project, key_id, *_ = search_client
    fake.pages = [html_page([1])]
    rt.auth.rate("search:" + project["id"] + ":brave", 1)
    rt.db.execute(
        "UPDATE limits SET count=6 WHERE bucket=?", ("search:" + project["id"] + ":brave",)
    )
    row = await complete(
        client, {"query": "robot agriculture", "engine": "auto", "strategy": "merge"}
    )
    assert row["status"] == "failed" and row["result"]["partial"]
    assert row["result"]["results"][0]["source_engines"] == ["duckduckgo"]
    assert row["error"]["details"]["partial_results"][0]["source_engines"] == ["duckduckgo"]
    rt.db.execute("UPDATE api_keys SET rate_limit=1 WHERE id=?", (key_id,))
    response = await client.get("/v1/projects/universrobot/key-info")
    assert response.status_code == 429 and int(response.headers["Retry-After"]) >= 1
    assert response.json()["error"]["details"]["scope"] == "api_key"


@pytest.mark.parametrize(
    "failure",
    [
        PQError("TIMEOUT", "Timed out", 504),
        PQError("UPSTREAM_CHANGED", "Unexpected HTML", 502),
        PQError("RATE_LIMITED", "Engine throttled", 429),
    ],
)
async def test_errors_cleanup_without_fallback(search_client, failure):
    client, _, fake, *_ = search_client
    unrelated = await fake.new_tab(None)
    fake.pages = [failure]
    row = await complete(client, {"query": "robot agriculture", "engine": "duckduckgo"})
    assert row["status"] == "failed" and row["error"]["code"] == failure.code
    assert set(fake.tabs) == {unrelated.id} and len(fake.closed) == 1
    assert len(fake.calls) == 1
    if failure.code == "RATE_LIMITED":
        assert row["error"]["details"]["cause"] == "unknown"
        assert row["error"]["details"]["retry_at"] is None


async def test_captcha_resume_timeout_and_cancel_cleanup(search_client):
    client, rt, fake, *_ = search_client
    fake.challenge = True
    fake.pages = [html_page([1])]
    payload = {"query": "robot agriculture", "engine": "duckduckgo"}
    row = await complete(client, payload)
    assert row["status"] == "waiting_for_human" and len(fake.tabs) == 1
    await client.post(f"/v1/projects/universrobot/jobs/{row['id']}/resume")
    await rt.jobs.active[row["id"]].task
    assert rt.jobs.get(rt.db.project("universrobot"), row["id"])["status"] == "completed"
    assert not fake.tabs
    fake.pages = [html_page([2])]
    row = await complete(client, payload)
    await client.post(f"/v1/projects/universrobot/jobs/{row['id']}/cancel")
    await rt.jobs.active[row["id"]].task
    assert not fake.tabs
    rt.settings.human_timeout_seconds = 0.02
    fake.pages = [html_page([3])]
    response = await client.post("/v1/projects/universrobot/search", json=payload)
    await rt.jobs.active[response.json()["job_id"]].task
    row = rt.jobs.get(rt.db.project("universrobot"), response.json()["job_id"])
    assert row["status"] == "failed" and row["error"]["code"] == "TIMEOUT" and not fake.tabs


@pytest.mark.parametrize(
    "overrides,reason",
    [
        ({"search_max_pages": 1}, "page_limit"),
        ({"search_max_total_results": 1}, "total_results_limit"),
    ],
)
async def test_chain_bounds(search_client, overrides, reason):
    client, rt, fake, project, *_ = search_client
    rt.db.execute("UPDATE projects SET config=? WHERE id=?", (json.dumps(overrides), project["id"]))
    fake.pages = [html_page([1, 2], next_offset=2)]
    result = (await complete(client, {"query": "robot agriculture", "engine": "duckduckgo"}))[
        "result"
    ]
    assert result["has_more"] is False and result["next_cursor"] is None
    assert result["stop_reason"] == reason and result["partial"]


def test_next_form_rejects_bad_origin_query_and_preserves_fields():
    for bad in (
        "https://evil.example/html/",
        "https://html.duckduckgo.com.evil/html/",
        "http://127.0.0.1/html/",
        "https://html.duckduckgo.com/anomaly.js",
        "https://user:password@html.duckduckgo.com/html/",
    ):
        html = html_page([1], next_offset=1).replace('action="/html/"', f'action="{bad}"')
        assert (
            ddg_continuation(html, ADAPTERS["duckduckgo"].base, "robot agriculture")[2]
            == "continuation_unusable"
        )
    assert (
        ddg_continuation(html_page([1], next_offset=1), ADAPTERS["duckduckgo"].base, "other")[0]
        is None
    )


async def test_queued_cancellation_releases_claim_and_preserves_other_tabs(search_client):
    client, rt, fake, project, *_ = search_client
    fake.pages = [html_page([1], next_offset=1)]
    payload = {"query": "robot agriculture", "engine": "duckduckgo"}
    cursor = (await complete(client, payload))["result"]["next_cursor"]
    unrelated = await fake.new_tab(project)
    rt.jobs.semaphore = asyncio.Semaphore(0)
    response = await client.post(
        "/v1/projects/universrobot/search", json={**payload, "cursor": cursor}
    )
    job_id = response.json()["job_id"]
    await asyncio.sleep(0.01)
    await client.post(f"/v1/projects/universrobot/jobs/{job_id}/cancel")
    await rt.jobs.active[job_id].task
    assert (
        rt.db.one(
            "SELECT claimed_job_id FROM search_cursors WHERE token_hash=?", (digest(cursor),)
        )["claimed_job_id"]
        is None
    )
    assert set(fake.tabs) == {unrelated.id}
    rt.jobs.semaphore = asyncio.Semaphore(1)
    fake.pages = [html_page([2], no_more=True)]
    assert (await complete(client, {**payload, "cursor": cursor}))["status"] == "completed"


async def test_cursor_capacity_and_shared_engine_quota(search_client):
    client, rt, fake, project, *_ = search_client
    rt.db.execute(
        "UPDATE projects SET config=? WHERE id=?",
        ('{"search_max_cursors_per_project":1}', project["id"]),
    )
    fake.pages = [html_page([1], next_offset=1), html_page([2], next_offset=2)]
    payload = {"query": "robot agriculture", "engine": "duckduckgo"}
    assert (await complete(client, payload))["result"]["next_cursor"]
    result = (await complete(client, payload))["result"]
    assert result["stop_reason"] == "cursor_capacity" and result["partial"]
    assert result["next_cursor"] is None and result["returned_count"] == 1
    _, token = rt.auth.create_key(project, "Another key", ["search:read"])
    rt.db.execute(
        "UPDATE limits SET count=6 WHERE bucket=?", ("search:" + project["id"] + ":duckduckgo",)
    )
    result = await complete(client, payload, headers={"Authorization": "Bearer " + token})
    assert result["error"]["details"]["scope"] == "project_engine"
    assert len(fake.calls) == 2


async def test_actual_sqlite_reopen_retains_idempotency(search_client):
    from pagequay.auth import Auth
    from pagequay.storage import Storage

    client, rt, fake, project, key_id, *_ = search_client
    fake.pages = [html_page([1])]
    payload = {"query": "robot agriculture", "engine": "duckduckgo"}
    first = await complete(client, payload, headers={"Idempotency-Key": "durable"})
    db = Storage(rt.db.root)
    try:
        manager = Jobs(db, rt.settings, Auth(db, rt.settings), rt.events)

        async def must_not_run(job):
            pytest.fail("Replayed operation must not execute")

        replay = manager.submit(
            project,
            key_id,
            "search",
            "search:read",
            must_not_run,
            idempotency_key="durable",
            payload=Search(**payload).model_dump(),
        )
        assert replay["job_id"] == first["id"] and replay["idempotency_replayed"]
        assert not manager.active
    finally:
        db.close()


async def test_cancellation_during_tab_allocation_closes_only_its_page(search_client):
    client, rt, fake, project, *_ = search_client
    unrelated = await fake.new_tab(project)
    created, release = asyncio.Event(), asyncio.Event()
    original = fake.new_tab

    async def slow_allocation(project):
        tab = await original(project)
        created.set()
        await release.wait()
        return tab

    fake.new_tab = slow_allocation
    response = await client.post(
        "/v1/projects/universrobot/search",
        json={"query": "robot agriculture", "engine": "duckduckgo"},
    )
    job_id = response.json()["job_id"]
    await created.wait()
    rt.jobs.cancel(project, job_id)
    release.set()
    await rt.jobs.active[job_id].task
    assert rt.jobs.get(project, job_id)["status"] == "cancelled"
    assert set(fake.tabs) == {unrelated.id}


async def test_expired_cursor_state_is_erased_but_tombstone_reports_expiry(search_client):
    client, rt, fake, *_ = search_client
    fake.pages = [html_page([1, 2], next_offset=2)]
    payload = {"query": "robot agriculture", "engine": "duckduckgo", "limit": 1}
    cursor = (await complete(client, payload))["result"]["next_cursor"]
    rt.db.execute("UPDATE search_cursors SET expires_at=?", (time.time() - 60,))
    await rt.retention.sweep()
    row = rt.db.one("SELECT state FROM search_cursors WHERE token_hash=?", (digest(cursor),))
    assert row["state"] == "{}"
    response = await client.post(
        "/v1/projects/universrobot/search", json={**payload, "cursor": cursor}
    )
    assert response.status_code == 410


async def test_no_progress_empty_page_does_not_follow_next(search_client):
    client, _, fake, *_ = search_client
    fake.pages = [html_page([], next_offset=1, no_more=True)]
    result = (await complete(client, {"query": "robot agriculture", "engine": "duckduckgo"}))[
        "result"
    ]
    assert result["stop_reason"] == "no_progress"
    assert result["has_more"] is False and result["next_cursor"] is None


async def test_immediate_cancellation_before_runner_starts_releases_cursor(search_client):
    client, rt, fake, project, key_id, *_ = search_client
    fake.pages = [html_page([1], next_offset=1)]
    payload = {"query": "robot agriculture", "engine": "duckduckgo"}
    cursor = (await complete(client, payload))["result"]["next_cursor"]
    request = Search(**payload, cursor=cursor)
    submitted = rt.jobs.submit(
        project,
        key_id,
        "search",
        "search:read",
        lambda job: rt.search.search(project, request, job),
        reserve=lambda job: rt.search.claim(project, request, job),
    )
    task = rt.jobs.active[submitted["job_id"]].task
    rt.jobs.cancel(project, submitted["job_id"])
    await asyncio.gather(task, return_exceptions=True)
    assert submitted["job_id"] not in rt.jobs.active
    assert rt.jobs.get(project, submitted["job_id"])["status"] == "cancelled"
    assert (
        rt.db.one(
            "SELECT claimed_job_id FROM search_cursors WHERE token_hash=?", (digest(cursor),)
        )["claimed_job_id"]
        is None
    )


async def test_lowered_chain_cap_applies_to_cached_results(search_client):
    client, rt, fake, project, *_ = search_client
    fake.pages = [html_page([1, 2, 3, 4], next_offset=4)]
    payload = {"query": "robot agriculture", "engine": "duckduckgo", "limit": 1}
    cursor = (await complete(client, payload))["result"]["next_cursor"]
    rt.db.execute(
        "UPDATE projects SET config=? WHERE id=?", ('{"search_max_total_results":2}', project["id"])
    )
    result = (await complete(client, {**payload, "cursor": cursor, "limit": 50}))["result"]
    assert result["returned_count"] == 1 and result["results"][0]["rank"] == 2
    assert result["next_cursor"] is None and result["stop_reason"] == "total_results_limit"
    assert len(fake.calls) == 1
