import asyncio
import gzip
import json
import os
import sqlite3
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup
from conftest import login
from playwright.async_api import Error as PlaywrightError

from pagequay.audit import TabAudit, audit_url
from pagequay.errors import PQError
from pagequay.main import create_app
from pagequay.models import Actions, Navigate
from pagequay.network import NetworkPolicy
from pagequay.settings import Policy, Settings
from pagequay.storage import Storage


def test_audit_upgrade_preserves_old_events(tmp_path):
    conn = sqlite3.connect(tmp_path / "pagequay.sqlite3")
    conn.execute("CREATE TABLE schema_migrations(version TEXT PRIMARY KEY)")
    for path in sorted(files("pagequay").joinpath("migrations").iterdir(), key=lambda p: p.name):
        if path.name.endswith(".sql") and path.name < "005":
            conn.executescript(path.read_text())
            conn.execute("INSERT INTO schema_migrations VALUES (?)", (path.name,))
    conn.execute("INSERT INTO audit VALUES ('old',0,NULL,'admin','admin.login','ok')")
    conn.commit()
    conn.close()
    db = Storage(tmp_path)
    try:
        assert db.one("SELECT * FROM audit WHERE id='old'")["details"] == "{}"
        db.audit("test")
        assert db.one("SELECT count(*) AS n FROM audit")["n"] == 2
    finally:
        db.close()


def test_urls_keep_query_values_encoding_and_fragments():
    result = audit_url("https://user:password@example.org/page?token=secret&q=private#secret")
    assert result == "https://example.org/page?token=secret&q=private#secret"
    ddg_url = "https://html.duckduckgo.com/html/?q=robots+agricoles&kl=fr-fr"
    assert audit_url(ddg_url) == ddg_url
    encoded_url = "https://example.org/?q=a%2Bb%20c&tag=one&tag=two&empty=#section%201"
    assert audit_url(encoded_url) == encoded_url
    assert audit_url("http://[::1]:8080/page") == "http://[::1]:8080/page"
    for value in (
        "data:text/html,secret",
        "about:blank",
        "https://example.org:invalid/",
        "http://[",
    ):
        assert audit_url(value) is None


def test_audit_admin_details_filters_and_escaping(client, projects):
    rt = client.app.state.rt
    a, b, ka, *_ = projects
    rt.db.audit(
        "function.submit_search_form",
        a["id"],
        ka,
        details={
            "function": "submit_search_form",
            "label": "next page",
            "job_id": "job-a",
            "duration_ms": 2345,
            "url": "https://example.org/<script>",
            "result_url": "https://html.duckduckgo.com/html/?q=robots+agricoles&kl=fr-fr",
        },
    )
    rt.db.audit(
        "network.response",
        a["id"],
        details={
            "url": "https://example.org/page2",
            "job_id": "job-a",
            "downloaded_bytes": 2048,
            "resource_type": "document",
            "http_status": 200,
            "duration_ms": 125,
        },
    )
    rt.db.audit("function.navigate", b["id"], details={"job_id": "job-b"})
    assert client.get("/admin/audit", follow_redirects=False).status_code == 303
    login(client)
    response = client.get("/admin/audit?project=universrobot&job=job-a")
    assert response.status_code == 200
    assert "next page" in response.text and "2.00" in response.text
    durations = BeautifulSoup(response.text, "html.parser").select(".audit-duration")
    assert sorted(cell.get_text() for cell in durations) == ["125 ms", "2.35 s"]
    assert "&lt;script&gt;" in response.text and "<script>" not in response.text
    assert "q=robots+agricoles&amp;kl=fr-fr" in response.text
    assert "[masque]" not in response.text
    assert (
        "job-b"
        not in BeautifulSoup(response.text, "html.parser")
        .select_one(".audit-table tbody")
        .get_text()
    )
    assert (
        BeautifulSoup(response.text, "html.parser").select_one(
            'select[name="job"] option[value="job-a"]'
        )["selected"]
        == ""
    )
    response = client.get("/admin/audit?project=universrobot&category=functions")
    assert "function.submit_search_form" in response.text
    assert "function.navigate" not in response.text and "network.response" not in response.text
    response = client.get("/admin/audit?category=navigation&job=job-a")
    assert "network.response" in response.text and "next page</span>" not in response.text


def test_audit_datetime_bounds_honor_offsets_and_keep_selected_job(client, projects):
    rt = client.app.state.rt
    a, *_ = projects
    base = datetime(2026, 10, 10, 13, 20, 30, tzinfo=UTC).timestamp()
    for index, delta in enumerate((-1, 0, 10, 11)):
        rt.db.audit("date-marker-" + str(index), a["id"], details={"job_id": "date-job"})
        rt.db.execute(
            "UPDATE audit SET at=? WHERE action=?", (base + delta, "date-marker-" + str(index))
        )
    login(client)
    response = client.get(
        "/admin/audit",
        params={
            "job": "date-job",
            "since": "2026-10-10T15:20:30+02:00",
            "until": "2026-10-10T13:20:40Z",
        },
    )
    assert response.status_code == 200
    table = BeautifulSoup(response.text, "html.parser").select_one(".audit-table tbody").get_text()
    assert "date-marker-0" not in table and "date-marker-3" not in table
    assert "date-marker-1" in table and "date-marker-2" in table
    assert 'data-initial-date="2026-10-10T13:20:30+00:00"' in response.text
    assert client.get("/admin/audit", params={"since": "invalid"}).status_code == 400
    assert (
        client.get(
            "/admin/audit",
            params={"since": "2026-10-10T14:00:00Z", "until": "2026-10-10T13:00:00Z"},
        ).status_code
        == 400
    )
    # Preserve a directly linked selection even if its events are older than the menu limit.
    response = client.get("/admin/audit?job=older-selected-job")
    selected = BeautifulSoup(response.text, "html.parser").select_one(
        'select[name="job"] option[selected]'
    )
    assert selected["value"] == "older-selected-job"


async def test_errors_and_unavailable_sizes_do_not_leak_inputs(tmp_path):
    db = Storage(tmp_path)
    project = db.create_project("audit", "Audit")
    page = SimpleNamespace(url="https://example.org/?secret=private", on=lambda *_: None)
    telemetry = TabAudit(db, project, SimpleNamespace(id="tab", page=page), set())
    job = SimpleNamespace(id="job", key_id="key")
    try:
        with pytest.raises(PQError):
            async with telemetry.operation("fill", job):
                raise PQError("FORBIDDEN", "private form value")
        with pytest.raises(asyncio.CancelledError):
            async with telemetry.operation("navigate", job):
                raise asyncio.CancelledError()

        async def unavailable():
            raise PlaywrightError("private browser message")

        await telemetry.record_request(
            SimpleNamespace(sizes=unavailable), {"url": audit_url(page.url)}, False
        )
        await db.telemetry.flush_async()
        rows = db.all("SELECT * FROM audit WHERE action != 'project.created'")
        assert [row["status"] for row in rows] == ["error", "error", "ok"]
        assert json.loads(rows[-1]["details"])["downloaded_bytes"] is None
        assert all(json.loads(row["details"])["duration_ms"] >= 0 for row in rows[:2])
        assert "secret=private" in str(rows)
        assert "private form value" not in str(rows) and "private browser message" not in str(rows)
        assert telemetry.current == {}
    finally:
        db.close()


async def test_monotonic_durations_nested_operations_and_network_collection(tmp_path, monkeypatch):
    db = Storage(tmp_path)
    project = db.create_project("audit", "Audit")
    page = SimpleNamespace(url="https://example.org/", on=lambda *_: None)
    tasks = set()
    telemetry = TabAudit(db, project, SimpleNamespace(id="tab", page=page), tasks)
    clock = [10.0]
    monkeypatch.setattr("pagequay.audit.time.perf_counter", lambda: clock[0])

    class Request:
        url = page.url
        method = "GET"
        resource_type = "document"

        async def sizes(self):
            # Metadata collection must not inflate the transfer duration.
            clock[0] += 3
            return {"responseBodySize": 512}

    request = Request()
    try:
        async with telemetry.operation("actions", None):
            clock[0] = 11
            async with telemetry.operation("click", None):
                telemetry.started(request)
                clock[0] = 11.125
                telemetry.response(SimpleNamespace(request=request, status=200))
                telemetry.finish(request, False)
                await asyncio.gather(*tasks)
        await db.telemetry.flush_async()
        details = {
            row["action"]: json.loads(row["details"])
            for row in db.all("SELECT * FROM audit WHERE action != 'project.created'")
        }
        assert details["network.response"]["duration_ms"] == 125
        assert details["function.click"]["duration_ms"] == 3125
        assert details["function.actions"]["duration_ms"] == 4125
        assert telemetry.current == {} and telemetry.requests == {}
    finally:
        db.close()


@pytest.mark.browser
@pytest.mark.skipif(os.environ.get("PQ_BROWSER_TESTS") != "1", reason="Use --browser")
async def test_browser_audit_redirect_size_next_page_and_native_form(tmp_path):
    html = (
        b'<html><body><input id="field"><img src="/asset">'
        b'<a id="next" aria-label="Next page" href="/next">Next page</a></body></html>'
    )
    compressed = gzip.compress(html)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path.startswith("/redirect"):
                self.send_response(302)
                self.send_header("Location", "/start?token=redirect-secret")
                self.end_headers()
                return
            payload = compressed if self.path.startswith("/start") else b"<html>Next</html>"
            self.send_response(404 if self.path == "/missing" else 200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(payload)))
            if self.path.startswith("/start"):
                self.send_header("Content-Encoding", "gzip")
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(303)
            self.send_header("Location", "/next?token=post-secret")
            self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_port
    base = f"http://localhost:{port}"
    app = create_app(
        Settings(data_dir=tmp_path, policy=Policy(headless=True)),
        network_factory=lambda policy: NetworkPolicy(
            policy, test_allowed_hosts={"localhost"}, test_ports={port}
        ),
    )
    try:
        async with app.router.lifespan_context(app):
            rt = app.state.rt
            project = rt.db.create_project("audit", "Audit")
            tab = await rt.browser.new_tab(project)
            job = SimpleNamespace(
                id="job-one",
                key_id="key-one",
                set_tab=lambda _: None,
                check_authorization=lambda: None,
            )
            await rt.browser.navigate(project, Navigate(url=base + "/redirect"), job, tab.id)
            await rt.browser.actions(
                project,
                tab.id,
                Actions(
                    actions=[
                        {"type": "fill", "selector": "#field", "value": "form-secret"},
                        {"type": "click", "selector": "#next"},
                    ]
                ),
                job,
            )
            job.id, job.key_id = "job-two", "key-two"
            await rt.browser.submit_search_form(
                project,
                tab.id,
                {"url": base + "/post", "method": "post", "fields": [["q", "post-body-secret"]]},
                job,
            )
            if rt.browser.audit_tasks:
                await asyncio.gather(*rt.browser.audit_tasks)
            await rt.db.telemetry.flush_async()
            rows = rt.db.all("SELECT * FROM audit")
            details = [json.loads(row["details"]) for row in rows]
            measured = [
                d
                for r, d in zip(rows, details, strict=True)
                if r["action"].startswith(("network.", "function."))
            ]
            assert measured and all(d["duration_ms"] >= 0 for d in measured)
            redirect = next(d for d in details if d.get("http_status") == 302)
            assert redirect["redirect_url"] == base + "/start?token=redirect-secret"
            document = next(
                d
                for d in details
                if d.get("url") == base + "/start?token=redirect-secret" and "downloaded_bytes" in d
            )
            assert document["downloaded_bytes"] == len(compressed)
            assert document["job_id"] == "job-one"
            assert any(d.get("resource_type") == "image" for d in details)
            click = next(
                d for r, d in zip(rows, details, strict=True) if r["action"] == "function.click"
            )
            assert click["label"] == "next page" and click["result_url"] == base + "/next"
            form = next(
                d
                for r, d in zip(rows, details, strict=True)
                if r["action"] == "function.submit_search_form"
            )
            assert form["label"] == "next page"
            assert form["result_url"] == base + "/next?token=post-secret"
            assert form["job_id"] == "job-two"
            assert next(r for r in rows if r["action"] == "function.click")["actor"] == "key-one"
            assert all(secret not in str(rows) for secret in ("post-body-secret", "form-secret"))
            assert "[masque]" not in str(rows)
            await tab.page.goto(base + "/missing")
            await tab.page.evaluate(
                "url => fetch(url).catch(() => null)", f"http://127.0.0.1:{port}/private"
            )
            if rt.browser.audit_tasks:
                await asyncio.gather(*rt.browser.audit_tasks)
            await rt.db.telemetry.flush_async()
            assert (
                rt.db.one(
                    "SELECT status FROM audit WHERE json_extract(details, '$.http_status')=404"
                )["status"]
                == "error"
            )
            failure = rt.db.one("SELECT * FROM audit WHERE action='network.failed'")
            assert failure["status"] == "error"
            assert json.loads(failure["details"])["duration_ms"] >= 0
            assert json.loads(failure["details"])["downloaded_bytes"] is None
            # Manual navigation is attributed to the browser, not the last API job.
            await tab.page.goto(base + "/manual")
            await rt.browser.close_tab(project, tab.id)
            if rt.browser.audit_tasks:
                await asyncio.gather(*rt.browser.audit_tasks)
            await rt.db.telemetry.flush_async()
            manual = next(
                r
                for r in rt.db.all("SELECT * FROM audit WHERE action='tab.visited'")
                if json.loads(r["details"])["url"] == base + "/manual"
            )
            assert manual["actor"] == "browser"
            assert "job_id" not in json.loads(manual["details"])
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
