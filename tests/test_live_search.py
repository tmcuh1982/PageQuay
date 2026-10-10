import asyncio
import json
import time
from pathlib import Path

import httpx
import pytest

from pagequay.main import create_app
from pagequay.models import Search
from pagequay.settings import Policy, Settings

OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "testing"


async def test_live_duckduckgo_reports_actual_result(tmp_path, request):
    if not request.config.getoption("--live"):
        pytest.skip("Use --live to attempt an external search")
    app = create_app(
        Settings(
            data_dir=tmp_path,
            policy=Policy(headless=True),
            job_timeout_seconds=60,
            human_timeout_seconds=5,
        )
    )
    async with app.router.lifespan_context(app):
        rt = app.state.rt
        project = rt.db.create_project("live-check", "Live check")
        events = rt.events.subscribe(project["id"])
        model = Search(query="Playwright Python documentation", engine="duckduckgo", limit=3)
        value = rt.jobs.submit(
            project,
            None,
            "search",
            "search:read",
            lambda job: rt.search.search(project, model, job),
        )
        await asyncio.wait_for(rt.jobs.active[value["job_id"]].task, 75)
        row = rt.jobs.get(project, value["job_id"])
        observed = []
        while not events.empty():
            observed.append(events.get_nowait()["event"])
        rt.events.unsubscribe(project["id"], events)
        report = {
            "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "engine": "duckduckgo",
            "status": row["status"],
            "result": row["result"],
            "error": row["error"],
            "challenge_required_detected": "challenge.required" in observed,
            "note": "External availability check. A passing test does not imply successful search; "
            "inspect status.",
        }
        output = OUTPUT
        output.mkdir(exist_ok=True)
        (output / "duckduckgo-live.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        )
        print(json.dumps(report, ensure_ascii=False))
        assert row["status"] in {"completed", "failed", "waiting_for_human"}


async def test_live_google_api_and_content(tmp_path, request):
    if not request.config.getoption("--live"):
        pytest.skip("Use --live to attempt an external search")
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT / "google-content.txt").unlink(missing_ok=True)
    (OUTPUT / "google-live.png").unlink(missing_ok=True)
    app = create_app(
        Settings(
            data_dir=tmp_path,
            policy=Policy(headless=not request.config.getoption("--headed")),
            job_timeout_seconds=60,
            human_timeout_seconds=5,
        )
    )
    report = {
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "engine": "google",
        "query": "Playwright Python documentation",
        "client": "ASGI test client on Mac mini; MacBook Air path NOT tested",
        "search_succeeded": False,
        "content_retrieved": False,
    }
    async with app.router.lifespan_context(app):
        rt = app.state.rt
        project = rt.db.create_project("google-check", "Google API check")
        _, token = rt.auth.create_key(
            project, "Temporary test", ["search:read", "browser:interact", "content:read"]
        )
        events = rt.events.subscribe(project["id"])
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://127.0.0.1:8765",
            headers={"Authorization": "Bearer " + token},
        ) as client:

            async def complete(method, path, **kwargs):
                response = await client.request(method, path, **kwargs)
                assert response.status_code == 202, response.text
                value = response.json()
                await asyncio.wait_for(rt.jobs.active[value["job_id"]].task, 75)
                response = await client.get(value["url"])
                assert response.status_code == 200
                return response.json()

            prefix = "/v1/projects/google-check"
            search = await complete(
                "POST",
                prefix + "/search",
                json={"engine": "google", "query": report["query"], "limit": 3},
            )
            report["search"] = search
            results = (search.get("result") or {}).get("results", [])
            report["search_succeeded"] = search["status"] == "completed" and bool(results)
            if report["search_succeeded"]:
                target = next(
                    (row for row in results if row["url"].startswith("https://playwright.dev/")),
                    results[0],
                )
                report["source_url"] = target["url"]
                navigation = await complete("POST", prefix + "/tabs", json={"url": target["url"]})
                report["navigation"] = navigation
                if navigation["status"] == "completed":
                    tab_id = navigation["result"]["tab_id"]
                    extraction = await complete("GET", prefix + f"/tabs/{tab_id}/content")
                    report["extraction"] = extraction
                    if extraction["status"] == "completed":
                        artifact = await client.get(extraction["result"]["url"])
                        assert artifact.status_code == 200
                        content = artifact.text
                        (OUTPUT / "google-content.txt").write_text(content)
                        report["content_retrieved"] = bool(content.strip())
                        report["content_file"] = "google-content.txt"
                        report["content_characters"] = len(content)
                        report["content_excerpt"] = content[:1500]
            observed = []
            while not events.empty():
                observed.append(events.get_nowait()["event"])
            report["challenge_required_detected"] = "challenge.required" in observed
            rt.events.unsubscribe(project["id"], events)
            # Failure evidence is diagnostic only; no challenge is solved automatically.
            if search["status"] != "completed" and any(
                tab["tab_id"] == search.get("tab_id") for tab in rt.browser.list_tabs(project)
            ):
                tab = rt.browser.tab(project, search["tab_id"])
                report["diagnostic_url"] = tab.page.url
                report["diagnostic_title"] = await tab.page.title()
                report["diagnostic_excerpt"] = (await tab.page.locator("body").inner_text())[:1500]
                await tab.page.screenshot(path=str(OUTPUT / "google-live.png"))
    (OUTPUT / "google-live.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(report, ensure_ascii=False))
    # This is an opt-in diagnostic: a passing test alone does not prove external availability.
    assert report["search"]["status"] in {"completed", "failed", "waiting_for_human"}


async def test_live_duckduckgo_native_continuations(tmp_path, request):
    if not request.config.getoption("--live"):
        pytest.skip("Use --live for bounded DuckDuckGo pagination evidence")
    OUTPUT.mkdir(exist_ok=True)
    app = create_app(
        Settings(
            data_dir=tmp_path,
            policy=Policy(headless=True),
            job_timeout_seconds=25,
            human_timeout_seconds=5,
        )
    )
    report = {
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "transport": "real Chromium / PageQuay guarded proxy, temporary project",
        "deployed_service_test": False,
        "queries": [],
        "three_native_pages_verified": False,
    }
    async with app.router.lifespan_context(app):
        rt = app.state.rt
        project = rt.db.create_project("ddg-live-pages", "DuckDuckGo live pages")
        # Permit an entire native page in a slice so three slices can prove three fetches.
        rt.db.execute(
            "UPDATE projects SET config=? WHERE id=?", ('{"search_max_results":50}', project["id"])
        )
        original = rt.search.read_page
        evidence = []

        async def record_page(*args, **kwargs):
            tab = args[4]
            try:
                html = await original(*args, **kwargs)
            except Exception:
                html = await tab.page.content()
                file = OUTPUT / f"duckduckgo-native-{len(evidence) + 1}.html"
                file.write_text(html)
                evidence.append(
                    {
                        "file": file.name,
                        "url": tab.page.url,
                        "title": await tab.page.title(),
                        "success": False,
                    }
                )
                raise
            file = OUTPUT / f"duckduckgo-native-{len(evidence) + 1}.html"
            file.write_text(html)
            evidence.append(
                {
                    "file": file.name,
                    "url": tab.page.url,
                    "title": await tab.page.title(),
                    "success": True,
                }
            )
            return html

        rt.search.read_page = record_page
        for query, locale in [
            ("robot agriculture", "fr-FR"),
            ("agricultural robotics manufacturers", "en-US"),
            ("robots agricoles France", "fr-FR"),
        ]:
            entry = {
                "query": query,
                "locale": locale,
                "slices": [],
                "distinct_urls": 0,
                "native_pages": 0,
                "duplicate_urls": 0,
            }
            cursor, seen = None, set()
            for _ in range(3 if not report["queries"] else 1):
                model = Search(
                    query=query, locale=locale, engine="duckduckgo", limit=50, cursor=cursor
                )
                value = rt.jobs.submit(
                    project,
                    None,
                    "search",
                    "search:read",
                    lambda job, model=model: rt.search.search(project, model, job),
                    reserve=lambda job, model=model: rt.search.claim(project, model, job),
                )
                events = rt.events.subscribe(project["id"])
                await asyncio.wait_for(rt.jobs.active[value["job_id"]].task, 40)
                row = rt.jobs.get(project, value["job_id"])
                observed = []
                while not events.empty():
                    observed.append(events.get_nowait()["event"])
                rt.events.unsubscribe(project["id"], events)
                entry["slices"].append(
                    {
                        "status": row["status"],
                        "result": row["result"],
                        "error": row["error"],
                        "events": observed,
                    }
                )
                result = row["result"] or {}
                for hit in result.get("results", []):
                    entry["duplicate_urls"] += hit["url"] in seen
                    seen.add(hit["url"])
                entry["native_pages"] = max(entry["native_pages"], result.get("pages_fetched", 0))
                cursor = result.get("next_cursor")
                if row["status"] != "completed" or not cursor:
                    break
            entry["distinct_urls"] = len(seen)
            report["queries"].append(entry)
        report["three_native_pages_verified"] = report["queries"][0]["native_pages"] >= 3
        report["evidence"] = evidence
        report["internal_tabs_remaining"] = len(rt.browser.list_tabs(project))
        report["note"] = "Diagnostic only: success of the test is not proof of three live pages."
    (OUTPUT / "duckduckgo-pagination-live.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "three_native_pages_verified": report["three_native_pages_verified"],
                "queries": [
                    {
                        "query": e["query"],
                        "native_pages": e["native_pages"],
                        "distinct_urls": e["distinct_urls"],
                        "statuses": [s["status"] for s in e["slices"]],
                    }
                    for e in report["queries"]
                ],
            }
        )
    )
    assert report["internal_tabs_remaining"] == 0
