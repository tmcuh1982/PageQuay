import asyncio
import json
import os
import sqlite3
import threading
import time
from importlib.resources import files
from types import SimpleNamespace

import pytest
from conftest import login
from playwright.async_api import async_playwright

from pagequay.audit import TabAudit
from pagequay.bounds import bounded_json
from pagequay.errors import PQError
from pagequay.jobs import Jobs
from pagequay.page_reader import read_page, read_title
from pagequay.retention import Retention
from pagequay.settings import Settings
from pagequay.storage import Storage
from pagequay.usage import hourly_usage


def test_denied_request_storm_keeps_exact_counts_and_bounded_detail(client, projects):
    rt = client.app.state.rt
    sink = rt.db.telemetry
    sink.settings.audit_events_per_minute = 60
    sink.settings.audit_events_per_project_minute = 30
    for _ in range(300):
        assert client.get("/v1/projects/universrobot/key-info").status_code == 401
    assert sink.flush()
    rows = rt.db.all("SELECT * FROM audit WHERE action='api.request'")
    assert 0 < len(rows) <= 30
    data = hourly_usage(rt.db)
    assert sum(row["calls"] for row in data["rows"]) == 300
    assert sink.snapshot()["dropped"] >= 270
    assert client.get("/health/ready").status_code == 200
    login(client)
    assert "Audit détaillé partiel" in client.get("/admin/audit").text


def test_audit_queue_volume_and_essential_reserve(tmp_path, monkeypatch):
    settings = Settings(data_dir=tmp_path, audit_queue_size=16, audit_max_rows=100)
    db = Storage(tmp_path, settings)
    sink = db.telemetry
    started, release = threading.Event(), threading.Event()
    write = sink.write
    worker_connections = []

    def delayed(conn, rows, counters):
        worker_connections.append((conn is db.conn, threading.get_ident()))
        started.set()
        assert release.wait(3)
        return write(conn, rows, counters)

    monkeypatch.setattr(sink, "write", delayed)
    try:
        db.audit("network.response")
        with sink.condition:
            sink.condition.notify()
        assert started.wait(2)
        for _ in range(1000):
            db.audit("network.response", details={"url": "https://example.org/a"})
        db.audit("admin.login")
        with sink.condition:
            assert len(sink.detail) <= 16
            assert len(sink.essential) == 1
        assert sink.snapshot()["dropped"] >= 984
        release.set()
        assert sink.flush()
        assert db.one("SELECT id FROM audit WHERE action='admin.login'")
        # Age-independent cap: spread admissible bursts across windows in a disposable DB.
        for _ in range(12):
            with sink.condition:
                sink.admitted.clear()
            for _ in range(16):
                db.audit("network.response", details={"url": "https://example.org/b"})
            assert sink.flush()
        assert db.one("SELECT rows FROM audit_budget WHERE pool='detail'")["rows"] <= 100
        assert sink.snapshot()["trimmed"] > 0
        assert db.one("SELECT id FROM audit WHERE action='admin.login'")
        assert all(
            not shared and thread != threading.get_ident() for shared, thread in worker_connections
        )
        sink.settings.audit_max_bytes = 1_000_000
        for _ in range(2):
            for _ in range(16):
                db.audit("network.response", details={"bounded_detail": "z" * 60000})
            assert sink.flush()
        budget = db.one("SELECT rows,bytes FROM audit_budget WHERE pool='detail'")
        assert budget["bytes"] <= 1_000_000
        assert db.one("SELECT id FROM audit WHERE action='admin.login'")
        dropped = sink.snapshot()["dropped"]
        db.audit("network.response", details={"oversized": "z" * 65536})
        assert sink.snapshot()["dropped"] == dropped + 1
    finally:
        release.set()
        db.close()
    reopened = Storage(tmp_path, settings)
    try:
        reopened.telemetry.flush()
        assert reopened.one("SELECT value FROM telemetry_state WHERE name='trimmed'")["value"] > 0
    finally:
        reopened.close()


async def test_hanging_requests_and_metadata_workers_are_bounded(tmp_path):
    db = Storage(tmp_path)
    project = db.create_project("bounded", "Bounded")
    callbacks, tasks = {}, set()
    page = SimpleNamespace(on=lambda name, callback: callbacks.update({name: callback}))
    telemetry = TabAudit(db, project, SimpleNamespace(id="tab", page=page), tasks)
    release = asyncio.Event()

    class Request:
        url = "https://example.org/a"
        method = "GET"
        resource_type = "fetch"

        async def sizes(self):
            await release.wait()
            return {"responseBodySize": 1}

    requests = [Request() for _ in range(300)]
    try:
        for request in requests:
            telemetry.started(request)
        assert len(telemetry.requests) == 128
        for request in requests:
            telemetry.finish(request, False)
        assert len(tasks) == 32
        assert not telemetry.requests
        for request in requests:
            telemetry.started(request)
        assert len(telemetry.requests) <= 128
        callbacks["close"](None)
        assert not telemetry.requests
        release.set()
        await asyncio.gather(*tasks)
        assert not tasks
        assert db.telemetry.snapshot()["dropped"] > 0
    finally:
        release.set()
        await asyncio.gather(*tasks)
        await asyncio.to_thread(db.close)


def test_writer_failure_does_not_mask_http_and_retries_exact_totals(client, monkeypatch):
    sink = client.app.state.rt.db.telemetry
    real_write = sink.write
    failed = threading.Event()

    def unavailable(*args):
        failed.set()
        raise sqlite3.OperationalError("fixture unavailable")

    monkeypatch.setattr(sink, "write", unavailable)
    for _ in range(12):
        assert client.get("/v1/projects/missing/key-info").status_code == 401
    with sink.condition:
        sink.condition.notify()
    assert failed.wait(2)
    assert client.get("/health/ready").status_code == 200
    assert sink.snapshot()["failures"] > 0
    monkeypatch.setattr(sink, "write", real_write)
    for _ in range(100):
        if sink.flush():
            break
        time.sleep(0.01)
    else:
        pytest.fail("Writer did not recover")
    assert sum(row["calls"] for row in hourly_usage(client.app.state.rt.db)["rows"]) == 12


def test_counter_cardinality_overflow_preserves_totals(tmp_path):
    db = Storage(tmp_path)
    sink = db.telemetry
    try:
        # Hold the admission lock so this deterministic burst cannot be partially flushed.
        with sink.condition:
            for index in range(3000):
                sink.count_api("GET /v1/projects/{slug}/key-info", "project", str(index))
            assert len(sink.counters) <= 513
        assert sink.flush()
        assert db.one("SELECT sum(calls) AS n FROM api_usage_hourly")["n"] == 3000
        assert db.one("SELECT count(*) AS n FROM api_usage_hourly")["n"] <= 513
        assert sink.snapshot()["counter_grouped"] > 0
    finally:
        db.close()


async def test_oversized_job_result_and_mutated_partial_cannot_be_persisted(client, projects):
    rt = client.app.state.rt
    project = projects[0]
    jobs = Jobs(rt.db, Settings(data_dir=rt.db.root, max_content_bytes=1024), rt.auth, rt.events)

    async def hostile(job):
        return {"title": "x" * 5000}

    submitted = jobs.submit(project, None, "navigate", "browser:read", hostile)
    await jobs.active[submitted["job_id"]].task
    row = jobs.get(project, submitted["job_id"])
    assert row["status"] == "failed" and row["error"]["code"] == "INVALID_INPUT"
    assert row["result"] is None

    async def mutated(job):
        partial = {"title": "normal"}
        job.progress(partial)
        partial["title"] = "x" * 5000
        raise PQError("RATE_LIMITED", "Fixture", details={"partial": partial})

    submitted = jobs.submit(project, None, "search", "search:read", mutated)
    await jobs.active[submitted["job_id"]].task
    row = jobs.get(project, submitted["job_id"])
    assert row["status"] == "failed" and row["error"]["code"] == "RATE_LIMITED"
    assert row["result"] is None and row["error"]["details"]["truncated"] is True
    await jobs.shutdown()


def test_json_limits_cover_escape_expansion_nesting_and_normal_results():
    assert json.loads(bounded_json({"title": "Été 🐚"}, 128)) == {"title": "Été 🐚"}
    for value in ({"title": "x" * 129}, {"title": "🐚" * 20}, [0] * 20001):
        with pytest.raises(PQError) as error:
            bounded_json(value, 128)
        assert error.value.status == 413


def test_counter_backfill_once_preserves_history_on_reopen(tmp_path):
    conn = sqlite3.connect(tmp_path / "pagequay.sqlite3")
    conn.execute("CREATE TABLE schema_migrations(version TEXT PRIMARY KEY)")
    for path in sorted(files("pagequay").joinpath("migrations").iterdir(), key=lambda p: p.name):
        if path.name.endswith(".sql") and path.name < "006":
            conn.executescript(path.read_text())
            conn.execute("INSERT INTO schema_migrations VALUES (?)", (path.name,))
    endpoint = "GET /v1/projects/{slug}/tabs"
    for index in range(3):
        conn.execute(
            "INSERT INTO audit VALUES (?,?,NULL,'api','api.request','ok',?)",
            (str(index), time.time(), json.dumps({"endpoint": endpoint})),
        )
    conn.commit()
    conn.close()
    db = Storage(tmp_path)
    try:
        assert sum(row["calls"] for row in hourly_usage(db)["rows"]) == 3
        db.audit("api.request", actor="api", details={"endpoint": endpoint})
        assert db.telemetry.flush()
        assert sum(row["calls"] for row in hourly_usage(db)["rows"]) == 4
    finally:
        db.close()
    db = Storage(tmp_path)
    try:
        assert sum(row["calls"] for row in hourly_usage(db)["rows"]) == 4
    finally:
        db.close()


def test_persistent_counter_capacity_groups_dimensions_without_losing_calls(tmp_path):
    db = Storage(tmp_path)
    endpoint = "GET /v1/projects/{slug}/tabs"
    hour = int(time.time() // 3600) * 3600
    try:
        with db.conn:
            db.conn.executemany(
                "INSERT INTO api_usage_hourly VALUES (?,?,?,?,1)",
                [(hour, endpoint, "project", str(index)) for index in range(9000)],
            )
        db.telemetry.count_api(endpoint, "project", "new-key")
        assert db.telemetry.flush()
        assert db.one("SELECT count(*) AS n FROM api_usage_hourly")["n"] <= 8192
        assert db.one("SELECT sum(calls) AS n FROM api_usage_hourly")["n"] == 9001
        assert db.telemetry.snapshot()["counter_grouped"] > 0
    finally:
        db.close()


@pytest.mark.browser
@pytest.mark.skipif(os.environ.get("PQ_BROWSER_TESTS") != "1", reason="Use --browser")
async def test_real_renderer_bounds_resist_monkeypatches_and_keep_normal_content(monkeypatch):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, chromium_sandbox=True)
        try:
            page = await browser.new_page()
            attach = page.context.new_cdp_session
            methods = []

            async def checked_session(target):
                session = await attach(target)
                send = session.send

                async def checked_send(method, params=None):
                    methods.append(method)
                    assert method not in {"Page.getFrameTree", "Target.getTargetInfo"}
                    response = await send(method, params)
                    assert len(json.dumps(response)) < 210000
                    return response

                monkeypatch.setattr(session, "send", checked_send)
                return session

            monkeypatch.setattr(page.context, "new_cdp_session", checked_session)
            await page.set_content(
                "<!DOCTYPE html><title>Été</title><body><p>Bonjour 🐚</p></body>"
            )
            assert (await read_title(page))["title"] == "Été"
            assert await read_page(page, "text", 64) == "Bonjour 🐚"
            assert (await read_page(page, "html", 1024)).startswith("<!DOCTYPE html>")
            await page.evaluate("""() => {
                document.title = 'T'.repeat(200000);
                document.body.textContent = '🐚'.repeat(200000);
                String.prototype.slice = function() { return this.toString(); };
                window.TextEncoder = class { encode() { return new Uint8Array(); } };
                Object.defineProperty(HTMLElement.prototype,'innerText',{
                    get() {return 'z'.repeat(1000000);}
                });
                document.querySelectorAll = () => [];
                JSON.stringify = () => 'malicious';
            }""")
            # Frame names must never be retrieved wholesale before clipping the title.
            await page.evaluate("""() => {
                for (let i=0; i<8; i++) {
                    const frame = document.createElement('iframe');
                    frame.name = 'N'.repeat(20000);
                    document.body.appendChild(frame);
                }
            }""")
            info = await read_title(page)
            assert len(info["title"]) == 512 and info["title_truncated"] is True
            sample = await read_page(page, "challenge", 200000)
            assert len(sample["text"]) <= 20000 and "z" not in sample["text"]
            for kind in ("text", "html"):
                with pytest.raises(PQError) as error:
                    await read_page(page, kind, 2048)
                assert error.value.status == 413
            await page.goto("about:blank")
            await page.set_content("<body>abc</body>")
            await page.evaluate("document.body.textContent = '\\ud800x'")
            assert await read_page(page, "text", 64) == "�x"
            await page.set_content(
                '<a href="https://example.org/">Lien</a><meta name="description" content="normal">'
            )
            assert (await read_page(page, "links", 4096))[0]["text"] == "Lien"
            assert (await read_page(page, "metadata", 4096))["meta"][0]["content"] == "normal"
            assert "Runtime.callFunctionOn" in methods
        finally:
            await browser.close()


async def test_delayed_audit_writer_does_not_block_retention_or_server_reads(tmp_path, monkeypatch):
    db = Storage(tmp_path)
    started, release = threading.Event(), threading.Event()
    write = db.telemetry.write

    def delayed(conn, rows, counters):
        started.set()
        assert release.wait(3)
        return write(conn, rows, counters)

    monkeypatch.setattr(db.telemetry, "write", delayed)
    try:
        db.audit("network.response")
        with db.telemetry.condition:
            db.telemetry.condition.notify()
        assert await asyncio.to_thread(started.wait, 2)
        retention = Retention(
            db, SimpleNamespace(states={}), None, SimpleNamespace(purge=lambda: None)
        )
        before = time.monotonic()
        await retention.sweep()
        db.all("SELECT * FROM audit")
        db.all("SELECT * FROM api_usage_hourly")
        assert time.monotonic() - before < 0.2
        release.set()
        assert await db.telemetry.flush_async()
    finally:
        release.set()
        await asyncio.to_thread(db.close)
