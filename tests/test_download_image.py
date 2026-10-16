import asyncio
import hashlib
import io
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
from PIL import Image

from pagequay.errors import PQError
from pagequay.image_download import verify_image
from pagequay.image_validator import validate_image
from pagequay.main import create_app
from pagequay.models import DownloadImage
from pagequay.network import NetworkPolicy
from pagequay.settings import Policy, Settings


def original(format="PNG"):
    out = io.BytesIO()
    Image.new("RGB", (32, 24), "blue").save(out, format=format)
    return out.getvalue()


@pytest.mark.parametrize(
    "format,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp")]
)
def test_integrity(format, mime):
    data = original(format)
    verify_image(data, mime)
    for bad in (data[: len(data) // 2], b"<html>challenge</html>"):
        with pytest.raises(PQError, match="validation"):
            verify_image(bad, mime)
    with pytest.raises(PQError):
        verify_image(data, "image/unknown")


@pytest.fixture
async def image_site(tmp_path, monkeypatch):
    # Fixture HTTP is permitted only via dependency injection. Production remains HTTPS/443.
    for module in ("pagequay.api", "pagequay.browser", "pagequay.navigation"):
        monkeypatch.setattr(module + ".require_https", lambda url: None)
    data = original()
    hits = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            hits.append(self.path)
            if self.path in {"/redirect", "/private-redirect"}:
                self.send_response(302)
                self.send_header(
                    "Location",
                    "http://10.0.0.1/private" if self.path == "/private-redirect" else "/image",
                )
                self.end_headers()
                return
            body, mime = data, "image/png"
            if self.path in {"/jpeg", "/webp"}:
                format = "JPEG" if self.path == "/jpeg" else "WEBP"
                body, mime = original(format), "image/" + format.lower()
            if self.path.startswith("/second-") and hits.count(self.path) >= 2:
                if self.path in {"/second-redirect", "/second-private"}:
                    self.send_response(302)
                    self.send_header(
                        "Location",
                        "/image" if self.path == "/second-redirect" else "http://10.0.0.1/private",
                    )
                    self.end_headers()
                    return
                if self.path == "/second-html":
                    body, mime = b"<html>challenge</html>", "text/html"
                if self.path == "/second-truncated":
                    body = data[:20]
            if self.path in {"/html", "/automatic", "/captcha", "/race"}:
                mime = "text/html"
                body = {
                    "/html": b"<h1>HTML</h1>",
                    "/race": b"<title>Just a moment</title>Checking your browser"
                    b"<script>setTimeout(()=>location.href='/slow',200);"
                    b"setTimeout(()=>location.href='/image',500)</script>",
                    "/captcha": b"<title>Verify you are human</title><p>Verify you are human</p>",
                    "/automatic": b"<title>Just a moment</title>Checking your browser"
                    b"<script>setTimeout(()=>location.href='/image',500)</script>",
                }[self.path]
            if self.path == "/fake-image":
                body = b"<html>challenge</html>"
            if self.path == "/truncated":
                body = data[:20]
            self.send_response(503 if self.path == "/503" else 200)
            self.send_header("Content-Type", mime)
            if self.path == "/second-oversize" and hits.count(self.path) >= 2:
                self.send_header("Content-Length", "5000001")
                self.end_headers()
                return
            if self.path == "/attachment":
                self.send_header("Content-Disposition", 'attachment; filename="image.png"')
            if self.path not in {"/no-length", "/oversize", "/slow"}:
                self.send_header(
                    "Content-Length",
                    str(
                        len(data) if self.path in {"/truncated", "/second-truncated"} else len(body)
                    ),
                )
            self.end_headers()
            try:
                if self.path == "/slow":
                    self.wfile.write(data[:8])
                    self.wfile.flush()
                    time.sleep(3)
                    body = data[8:]
                if self.path == "/oversize":
                    body = data * 1000
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def network(policy):
        return NetworkPolicy(
            policy, test_allowed_hosts={"localhost"}, test_ports={server.server_port}
        )

    app = create_app(
        Settings(data_dir=tmp_path, allowed_hosts=["testserver"], policy=Policy(headless=True)),
        network_factory=network,
    )
    try:
        async with app.router.lifespan_context(app):
            rt = app.state.rt
            from playwright.async_api import CDPSession

            send = CDPSession.send

            async def guarded_send(session, method, params=None):
                assert method not in {
                    "Fetch.getResponseBody",
                    "Fetch.takeResponseBodyAsStream",
                    "IO.read",
                    "Network.getResponseBody",
                    "Page.captureScreenshot",
                }
                if method == "Fetch.fulfillRequest":
                    assert "body" not in params
                if method == "Page.createIsolatedWorld":
                    assert not params.get("grantUniveralAccess")
                return await send(session, method, params)

            async def forbidden_screenshot(*args, **kwargs):
                raise AssertionError("Image acquisition must never request a screenshot")

            monkeypatch.setattr(CDPSession, "send", guarded_send)
            monkeypatch.setattr(rt.browser, "_screenshot", forbidden_screenshot)
            p = rt.db.create_project("images", "Images")
            key, token = rt.auth.create_key(p, "Test", ["browser:interact", "content:read"])
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
                headers={"Authorization": "Bearer " + token},
            ) as client:
                yield rt, p, key, client, f"http://localhost:{server.server_port}", data, hits
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def browser_test(function):
    import os

    function = pytest.mark.skipif(
        os.environ.get("PQ_BROWSER_TESTS") != "1", reason="Use --browser"
    )(function)
    return pytest.mark.browser(function)


async def start(site, path, **kwargs):
    rt, p, key, client, base, data, hits = site
    response = await client.post(
        "/v1/projects/images/download_image",
        json={"url": base + path, "expected_url": base + path, "timeout": 10, **kwargs},
    )
    assert response.status_code == 202, response.text
    return response.json()


async def finish(site, accepted):
    rt, _, _, client, *_ = site
    job = rt.jobs.active.get(accepted["job_id"])
    if job:
        await asyncio.wait_for(job.task, 20)
    return (await client.get(accepted["url"])).json()


@browser_test
@pytest.mark.parametrize(
    "path",
    [
        "/image",
        "/no-length",
        "/redirect",
        "/automatic",
        "/attachment",
        "/jpeg",
        "/webp",
    ],
)
async def test_browser_binary(image_site, path):
    rt, p, key, client, base, data, hits = image_site
    row = await finish(
        image_site,
        await start(
            image_site,
            path,
            expected_url=base + "/image" if path in {"/redirect", "/automatic"} else base + path,
        ),
    )
    assert row["status"] == "completed", row
    result = row["result"]
    if path in {"/jpeg", "/webp"}:
        data = original("JPEG" if path == "/jpeg" else "WEBP")
    content = await client.get(result["url"])
    assert content.content == data
    assert result["sha256"] == hashlib.sha256(data).hexdigest()
    assert result["media_type"] == (
        "image/" + path[1:] if path in {"/jpeg", "/webp"} else "image/png"
    )
    assert result["size"] == len(data)
    assert result["frame_id"]
    if path == "/redirect":
        assert result["redirect_chain"][0]["target_url"] == base + "/image"
    assert not rt.browser.list_tabs(p)
    other = rt.db.create_project("other", "Other")
    _, token = rt.auth.create_key(other, "Other", ["content:read"])
    assert (
        await client.get(result["url"], headers={"Authorization": "Bearer " + token})
    ).status_code == 403
    rt.db.execute("UPDATE artifacts SET expires_at=0")
    assert (await client.get(result["url"])).status_code == 404
    rt.artifacts.purge()
    assert not list((rt.db.root / "artifacts").iterdir())


@browser_test
@pytest.mark.parametrize(
    "path,kwargs,code",
    [
        ("/redirect", {}, "scope_changed"),
        ("/redirect", {"allow_redirects": False}, "REDIRECT_BLOCKED"),
        ("/html", {}, "IMAGE_HTML_RESPONSE"),
        ("/fake-image", {}, "IMAGE_INVALID"),
        ("/private-redirect", {}, "NAVIGATION_BLOCKED"),
        ("/captcha", {"timeout": 2}, "HUMAN_REQUIRED_TIMEOUT"),
        ("/truncated", {}, "IMAGE_INCOMPLETE"),
        ("/oversize", {"max_bytes": 100}, "IMAGE_TOO_LARGE"),
        ("/image", {"max_bytes": 10}, "IMAGE_TOO_LARGE"),
        ("/slow", {"timeout": 1}, "IMAGE_TIMEOUT"),
        ("/503", {}, "IMAGE_HTTP_STATUS"),
        ("/second-redirect", {}, "scope_changed"),
        ("/second-private", {}, "NAVIGATION_BLOCKED"),
        ("/second-html", {}, "IMAGE_HTML_RESPONSE"),
        ("/second-oversize", {}, "IMAGE_TOO_LARGE"),
        ("/second-truncated", {}, "IMAGE_INCOMPLETE"),
    ],
)
async def test_browser_refusals(image_site, path, kwargs, code):
    rt, p, *_ = image_site
    row = await finish(image_site, await start(image_site, path, **kwargs))
    assert row["status"] == "failed", row
    assert row["error"]["code"] == code, row
    assert row["error"]["details"]["partial_artifact"] is False
    assert row["error"]["details"]["cleanup_verified"] is True
    assert not rt.db.all("SELECT * FROM artifacts WHERE scope='content:read'")
    assert not rt.browser.list_tabs(p)


@browser_test
async def test_human_cancel_cleanup(image_site):
    rt, p, key, client, *_ = image_site
    accepted = await start(image_site, "/captcha")
    job = rt.jobs.active[accepted["job_id"]]
    async with asyncio.timeout(10):
        while job.status != "waiting_for_human":  # noqa: ASYNC110
            await asyncio.sleep(0.05)
    row = (await client.get(accepted["url"])).json()
    assert row["result"]["tab_id"] == accepted["tab_id"]
    assert row["result"]["capture"] is None
    assert not rt.db.all("SELECT * FROM artifacts")
    assert (await client.post(accepted["url"] + "/cancel")).status_code == 200
    await job.task
    assert job.status == "cancelled"
    assert not rt.browser.list_tabs(p)
    assert not rt.db.all("SELECT * FROM artifacts WHERE scope='content:read'")


@browser_test
async def test_image_human_resume_keeps_job_and_requires_explicit_resume(image_site):
    from playwright.async_api import Error as PlaywrightError

    rt, p, key, client, base, data, _ = image_site
    accepted = await start(image_site, "/captcha", expected_url=base + "/image")
    job = rt.jobs.active[accepted["job_id"]]
    async with asyncio.timeout(10):
        while job.status != "waiting_for_human":  # noqa: ASYNC110
            await asyncio.sleep(0.01)
    tab = rt.browser.tab(p, accepted["tab_id"])
    manual_navigation = asyncio.create_task(tab.page.goto(base + "/image"))
    async with asyncio.timeout(5):
        while tab.response_handler.final_url is None:  # noqa: ASYNC110
            await asyncio.sleep(0.01)
    assert job.status == "waiting_for_human"
    assert not rt.db.all("SELECT * FROM artifacts")
    assert (await client.post(accepted["url"] + "/resume")).status_code == 200
    row = await finish(image_site, accepted)
    try:
        await manual_navigation
    except PlaywrightError:
        pass  # The admitted image navigation is intentionally aborted before bootstrap.
    assert row["id"] == accepted["job_id"]
    assert row["tab_id"] == accepted["tab_id"]
    assert row["status"] == "completed", row
    assert (await client.get(row["result"]["url"])).content == data
    assert not rt.browser.list_tabs(p)


@pytest.mark.parametrize(
    "format,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp")]
)
async def test_disposable_decoder(format, mime):
    await validate_image(original(format), mime)
    with pytest.raises(PQError, match="bounded decoder"):
        await validate_image(b"invalid", mime)


async def test_decoder_cancel_reaps_child(monkeypatch):
    import asyncio
    import sys

    spawn = asyncio.create_subprocess_exec
    children = []

    async def slow_decoder(*args, **kwargs):
        child = await spawn(sys.executable, "-c", "import time; time.sleep(30)", **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(asyncio, "create_subprocess_exec", slow_decoder)
    task = asyncio.create_task(validate_image(original(), "image/png"))
    async with asyncio.timeout(3):
        while not children:  # noqa: ASYNC110
            await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 3)
    assert children[0].returncode is not None


def test_invalid_image_request_correlates_without_echoing_secrets(client):
    response = client.post(
        "/v1/projects/images/download_image",
        json={
            "url": "https://example.org/a",
            "max_bytes": 5_000_001,
            "do-not-echo-name": "do-not-echo-value",
        },
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["request_id"] == response.headers["x-request-id"]
    assert error["details"]["stage"] == "admission"
    assert error["details"]["version"]
    assert error["details"]["observed_at"]
    assert "do-not-echo" not in response.text


@pytest.mark.parametrize("chunked", [False, True])
def test_oversized_admission_retains_diagnostic(client, chunked):
    body = b" " * 66_000
    response = client.post(
        "/v1/projects/images/download_image",
        content=iter([body]) if chunked else body,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    error = response.json()["error"]
    assert error["request_id"] == response.headers["x-request-id"]
    assert error["details"]["cause"] == "payload_limit"
    assert error["details"]["version"]


async def test_dimension_limit_is_checked_before_decoding():
    import struct
    import zlib

    data = bytearray(original())
    data[16:24] = struct.pack(">II", 6_000, 5_000)
    data[29:33] = struct.pack(">I", zlib.crc32(data[12:29]))
    with pytest.raises(PQError) as caught:
        verify_image(bytes(data), "image/png")
    assert str(caught.value.__cause__) == "pixel_limit"
    with pytest.raises(PQError):
        await validate_image(bytes(data), "image/png")


def test_contract_and_auth(client, projects):
    _, _, _, _, token, _ = projects
    url = "https://example.org/image.png"
    response = client.post(
        "/v1/projects/universrobot/download_image",
        headers={"Authorization": "Bearer " + token},
        json={"url": url, "expected_url": url},
    )
    assert response.status_code == 403
    with pytest.raises(ValueError):
        DownloadImage(url=url, expected_url=url, max_bytes=5_000_001)


@browser_test
async def test_queue_deadline(image_site):
    rt, p, *_ = image_site
    slots = rt.db.policy().max_concurrent_jobs
    for _ in range(slots):
        await rt.jobs.semaphore.acquire()
    try:
        row = await finish(image_site, await start(image_site, "/image", timeout=0.1))
        assert row["status"] == "failed", row
        assert row["error"]["code"] == "IMAGE_TIMEOUT"
        assert row["error"]["details"]["stage"] == "queue"
        assert not rt.browser.list_tabs(p)
    finally:
        for _ in range(slots):
            rt.jobs.semaphore.release()


@browser_test
@pytest.mark.parametrize("action", ["cancel", "revoke"])
async def test_active_stream_abandon(image_site, action):
    rt, p, key, client, *_ = image_site
    # Ensure the small operation timeout is testing acquisition, not a cold browser launch.
    await rt.browser.start(p)
    accepted = await start(image_site, "/slow")
    job = rt.jobs.active[accepted["job_id"]]
    async with asyncio.timeout(5):
        while True:  # noqa: ASYNC110
            tab = rt.browser.states[p["id"]].tabs.get(accepted["tab_id"])
            if tab and tab.response_handler and tab.response_handler.stage == "acquisition":
                break
            await asyncio.sleep(0.01)
    if action == "cancel":
        (await client.post(accepted["url"] + "/cancel")).raise_for_status()
    else:
        rt.db.execute("UPDATE api_keys SET scopes=? WHERE id=?", ('["content:read"]', key))
    await asyncio.wait_for(job.task, 8)
    row = rt.jobs.get(p, job.id)
    assert row["status"] in {"cancelled", "failed"}, row
    assert row["error"]["details"]["cleanup_verified"] is True
    assert not rt.browser.list_tabs(p)
    assert not rt.db.all("SELECT * FROM artifacts WHERE scope='content:read'")


async def test_uncommitted_artifact_removed(client, projects):
    # Run on this event loop with an independent runtime's Jobs, not TestClient's service loop.
    from pagequay.jobs import Jobs

    rt = client.app.state.rt
    p, _, key, *_ = projects
    rt.db.execute(
        "UPDATE api_keys SET scopes=? WHERE id=?", ('["content:read","browser:interact"]', key)
    )
    jobs = Jobs(rt.db, rt.settings, rt.auth, rt.events)

    async def operation(job):
        artifact = rt.artifacts.put(p, original(), "image/png", image=True)
        job.uncommitted_artifact = artifact["artifact_id"]
        raise PQError("FORBIDDEN", "Fixture revoked authorization before terminal publication", 403)

    accepted = jobs.submit(p, key, "download_image", "content:read", operation)
    await jobs.active[accepted["job_id"]].task
    assert not rt.db.all("SELECT * FROM artifacts")
    assert not list((rt.db.root / "artifacts").iterdir())


async def test_failed_artifact_removal_is_terminal_and_reported(client, projects, monkeypatch):
    from pathlib import Path

    from pagequay.jobs import Jobs

    rt = client.app.state.rt
    project, _, key, *_ = projects
    rt.db.execute(
        "UPDATE api_keys SET scopes=? WHERE id=?", ('["content:read","browser:interact"]', key)
    )
    jobs = Jobs(rt.db, rt.settings, rt.auth, rt.events)
    unlink = Path.unlink
    created = []

    def denied(path, *args, **kwargs):
        if path.name in created:
            raise PermissionError("fixture: removal denied")
        return unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", denied)

    async def operation(job):
        artifact = rt.artifacts.put(project, original(), "image/png", image=True)
        created.append(artifact["artifact_id"])
        job.uncommitted_artifact = artifact["artifact_id"]
        job.cleanup_verified = True  # The owned tab closed before artifact rollback.
        raise PQError("FORBIDDEN", "Fixture revoked authorization", 403)

    accepted = jobs.submit(project, key, "download_image", "content:read", operation)
    await jobs.active[accepted["job_id"]].task
    row = jobs.get(project, accepted["job_id"])
    assert row["status"] == "failed"
    error = row["error"]
    assert error["code"] == "IMAGE_CLEANUP_FAILED"
    assert error["details"]["cleanup_verified"] is False
    assert error["details"]["previous_error"]["code"] == "FORBIDDEN"
    assert error["details"]["artifact_id"] == created[0]
    assert not rt.db.all("SELECT * FROM artifacts")  # Orphan is no longer downloadable.
    assert accepted["job_id"] not in jobs.active


def test_artifact_write_failure_cleans_partial(client, projects, monkeypatch):
    from pathlib import Path

    rt = client.app.state.rt
    p, *_ = projects

    def fail_write(path, data):
        with path.open("wb") as handle:
            handle.write(data[:5])
        raise OSError("Fixture: disk full")

    monkeypatch.setattr(Path, "write_bytes", fail_write)
    with pytest.raises(OSError):
        rt.artifacts.put(p, original(), "image/png", image=True)
    assert not rt.db.all("SELECT * FROM artifacts")
    assert not list((rt.db.root / "artifacts").iterdir())


def test_artifact_write_rollback_failure_is_explicit(client, projects, monkeypatch):
    from pathlib import Path

    rt = client.app.state.rt
    project, *_ = projects

    def fail_write(path, data):
        with path.open("wb") as handle:
            handle.write(data[:5])
        raise OSError("fixture: disk full")

    def fail_remove(path, **kwargs):
        raise PermissionError("fixture: removal denied")

    monkeypatch.setattr(Path, "write_bytes", fail_write)
    monkeypatch.setattr(Path, "unlink", fail_remove)
    with pytest.raises(PQError) as caught:
        rt.artifacts.put(project, original(), "image/png", image=True)
    assert caught.value.code == "IMAGE_CLEANUP_FAILED"
    assert caught.value.details["cleanup_verified"] is False
    assert caught.value.details["artifact_id"]
    assert caught.value.details["previous_error"]["code"] == "IMAGE_ARTIFACT_WRITE_FAILED"


@browser_test
async def test_concurrent_navigation_cannot_publish_previous_image(image_site):
    from playwright.async_api import Error as PlaywrightError

    rt, p, key, client, base, *_ = image_site
    accepted = await start(image_site, "/slow")
    async with asyncio.timeout(10):
        while True:  # noqa: ASYNC110
            tab = rt.browser.states.get(p["id"])
            tab = tab.tabs.get(accepted["tab_id"]) if tab else None
            if tab and tab.response_handler and tab.response_handler.streaming:
                break
            await asyncio.sleep(0.01)
    try:
        await tab.page.goto(base + "/image")
    except PlaywrightError:
        pass
    row = await finish(image_site, accepted)
    assert row["status"] == "failed", row
    assert row["error"]["code"] in {
        "scope_changed",
        "NAVIGATION_CHANGED",
        "IMAGE_INCOMPLETE",
        "IMAGE_INVALID",  # An interrupted body can reach EOF before the next response is observed.
        "IMAGE_ACQUISITION_FAILED",
    }, row
    assert not rt.db.all("SELECT * FROM artifacts WHERE scope='content:read'")
    assert not rt.browser.list_tabs(p)
