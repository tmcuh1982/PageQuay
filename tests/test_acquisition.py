import asyncio
import json
import socket
import time
from types import SimpleNamespace

import pytest
from playwright.async_api import Error as PlaywrightError

from pagequay.browser import Tab
from pagequay.errors import PQError
from pagequay.models import Navigate
from pagequay.navigation import NavigationEvidence, redirect_guard, require_https
from pagequay.network import NetworkPolicy
from pagequay.page_reader import isolated_read
from pagequay.settings import Policy
from pagequay.structured import extract_structured


class Frame:
    parent_frame = None
    child_frames = []
    name = "fixture"
    url = "https://example.org/doc"

    def is_detached(self):
        return False

    def locator(self, selector):
        frames = getattr(self, "dom_frames", self.child_frames)
        part = selector.split("=", 1)[1]
        if part == "overflow":
            return Owners([None] if len(frames) > 128 else [])
        index = int(part)
        return Owners([frames[index]] if index < len(frames) else [])


class Owners:
    def __init__(self, frames):
        self.frames = frames

    async def count(self):
        return len(self.frames)

    async def element_handle(self, **kwargs):
        return await self.nth(0).element_handle(**kwargs)

    def nth(self, index):
        owned = self.frames[index]

        class Handle:
            async def content_frame(self):
                return owned

            async def dispose(self):
                pass

        async def element_handle(**kwargs):
            return Handle()

        return SimpleNamespace(element_handle=element_handle)


class Page:
    def __init__(self):
        self.url = "https://example.org/doc"
        self.main_frame = Frame()
        self.frames = [self.main_frame]
        self.callbacks = {}

    def on(self, name, callback):
        self.callbacks[name] = callback

    def is_closed(self):
        return False


def request(page, url=None, parent=None, frame=None):
    return SimpleNamespace(
        url=url or page.url,
        redirected_from=parent,
        is_navigation_request=lambda: True,
        frame=frame or page.main_frame,
    )


@pytest.mark.parametrize("status", [200, 404])
def test_attested_main_response_never_infers_status_from_dom(status):
    page = Page()
    evidence = NavigationEvidence(page)
    req = request(page)
    evidence.request(req)
    evidence.response(
        SimpleNamespace(
            request=req, url=page.url, status=status, headers={"content-type": "text/html"}
        )
    )
    evidence.navigated(page.main_frame)
    proof = evidence.snapshot()
    assert proof["http_status"] == status and proof["http_status_reason"] is None
    assert proof["observed_at"].endswith("+00:00")
    # A 200 image cannot replace the main document's 404.
    evidence.response(
        SimpleNamespace(request=request(page, frame=Frame()), url=page.url, status=200, headers={})
    )
    assert evidence.snapshot()["http_status"] == status
    # set_content/browser DOM error: navigation with no HTTP response is unknown.
    evidence.navigated(page.main_frame)
    assert evidence.snapshot()["http_status"] is None
    assert evidence.snapshot()["http_status_reason"]


def test_same_url_reload_or_frame_change_invalidates_capture():
    page = Page()
    evidence = NavigationEvidence(page)
    before = evidence.checkpoint(page.url)
    evidence.request(request(page))
    with pytest.raises(PQError, match="changed"):
        evidence.verify(before, page.url)
    before = evidence.checkpoint(page.url)
    evidence.changed(Frame())
    with pytest.raises(PQError):
        evidence.verify(before, page.url)
    with pytest.raises(PQError) as error:
        evidence.checkpoint("https://example.org/other")
    assert error.value.code == "scope_changed"


@pytest.mark.parametrize("url", ["http://example.org/", "https://example.org:80/"])
def test_strict_https_and_ports(url):
    with pytest.raises(PQError):
        require_https(url)
    assert Navigate(url=url).allow_redirects is True  # old payload remains valid


@pytest.mark.parametrize(
    "address", ["10.0.0.1", "::1", "fe80::1", "fd00::1", "::ffff:127.0.0.1", "64:ff9b::a00:1"]
)
async def test_dns_ipv6_and_rebinding_are_typed(monkeypatch, address):
    answers = ["93.184.216.34", address]

    async def resolve(*args, **kwargs):
        return [
            (
                socket.AF_INET6 if ":" in answers[0] else socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                (answers.pop(0), 443),
            )
        ]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolve)
    policy = NetworkPolicy(Policy())
    await policy.resolve("https://example.org/doc")
    with pytest.raises(PQError) as error:
        await policy.resolve("https://example.org/doc")
    assert error.value.details["cause"] == "non_public_address"


class Session:
    def __init__(self, fault=None, paths=None):
        self.callbacks = {}
        self.calls = []
        self.fault = fault
        self.paths = paths or [[]]

    def on(self, name, callback):
        self.callbacks[name] = callback

    async def send(self, method, params=None):
        self.calls.append((method, params))
        if method == "Runtime.enable":
            for i in range(len(self.paths)):
                self.callbacks["Runtime.executionContextCreated"](
                    {"context": {"auxData": {"isDefault": True, "frameId": str(i)}}}
                )
        if method == "Page.createIsolatedWorld":
            return {"executionContextId": int(params["frameId"])}
        if method == "Runtime.callFunctionOn":
            if "arguments" not in params:
                value = (
                    True
                    if "return true" in params["functionDeclaration"]
                    else self.paths[params["executionContextId"]]
                )
                return {"result": {"value": value}}
            if isinstance(self.fault, BaseException):
                raise self.fault
            if self.fault == "js":
                return {"exceptionDetails": {"text": "Bearer SECRET page payload"}}
            if self.fault == "large":
                return {"result": {"value": json.dumps({"too_large": True})}}
            if self.fault == "schema":
                return {"result": {"value": "{}"}}
            return {"result": {"value": '{"value":{"truncated":false,"blocks":[]}}'}}
        return {}

    async def detach(self):
        pass


@pytest.mark.parametrize(
    ("fault", "code"),
    [
        (TimeoutError("SECRET"), "TIMEOUT"),
        ("js", "JAVASCRIPT_EXCEPTION"),
        ("large", "SIZE_LIMIT"),
        ("schema", "SCHEMA_REJECTED"),
        (PlaywrightError("SECRET"), "OTHER_ERROR"),
    ],
)
async def test_reader_causes_stages_and_sanitized_logs(fault, code, caplog):
    page = Page()
    session = Session(fault)

    async def connect(_):
        return session

    page.context = SimpleNamespace(new_cdp_session=connect)
    with pytest.raises(PQError) as error:
        await isolated_read(page, "function() {}", {}, max_bytes=1024)
    assert error.value.details["cause"] == code
    assert error.value.details["stage"] in {"extraction", "serialization"}
    assert "SECRET" not in caplog.text and "Bearer" not in caplog.text
    assert "exception_chain" in caplog.text


async def test_context_path_selects_cross_origin_child_without_page_js():
    page = Page()
    child = Frame()
    child.parent_frame = page.main_frame
    page.main_frame.child_frames = [child]
    session = Session(paths=[[], [0]])

    async def connect(_):
        return session

    page.context = SimpleNamespace(new_cdp_session=connect)
    result = await isolated_read(page, "function() {}", {}, frame=child, max_bytes=1024)
    assert result["blocks"] == []
    reads = [
        params
        for method, params in session.calls
        if method == "Runtime.callFunctionOn" and "arguments" in params
    ]
    assert reads[0]["executionContextId"] == 1
    session.paths = [[]]
    with pytest.raises(PQError) as error:
        await isolated_read(page, "function() {}", {}, frame=child, max_bytes=1024)
    assert error.value.details["cause"] == "WORLD_NOT_FOUND"


async def test_detached_child_preserves_legacy_reason_and_observed_fact(monkeypatch):
    page = Page()
    child = Frame()
    child.parent_frame = page.main_frame
    child.is_detached = lambda: True

    async def element():
        raise PlaywrightError("SECRET query?key=SECRET")

    child.frame_element = element
    page.frames.append(child)

    async def read(*args, **kwargs):
        return {"blocks": [], "truncated": False}

    monkeypatch.setattr("pagequay.structured.isolated_read", read)
    result = await extract_structured(page)
    entry = result["frames"][0]
    assert entry["reason"] == "frame_detached_or_unresponsive"
    assert entry["cause_code"] == "FRAME_DETACHED"
    assert entry["diagnostic"]["is_detached"] is True and result["partial"]


@pytest.mark.parametrize(
    "target", ["https://example.org/other?key=SECRET#SECRET", "https://other.org/doc"]
)
async def test_redirect_blocked_before_follow_and_safe_error(target):
    session = Session()
    page = Page()

    async def connect(_):
        return session

    async def resolve(_):
        pytest.fail("Exact redirect target must be rejected before DNS/follow")

    page.context = SimpleNamespace(new_cdp_session=connect)
    async with redirect_guard(
        page, SimpleNamespace(resolve=resolve), expected_url=page.url, allow_redirects=False
    ) as errors:
        session.callbacks["Fetch.requestPaused"](
            {
                "requestId": "r1",
                "resourceType": "Document",
                "request": {"url": page.url},
                "responseStatusCode": 302,
                "responseHeaders": [{"name": "Location", "value": target}],
            }
        )
        await asyncio.sleep(0)
        assert errors[0].code == "REDIRECT_BLOCKED"
        assert "SECRET" not in json.dumps(errors[0].details)
        assert any(method == "Fetch.failRequest" for method, _ in session.calls)
        assert not any(method == "Fetch.continueRequest" for method, _ in session.calls)


def wait_job(client, accepted):
    for _ in range(100):
        row = client.get(accepted["url"]).json()
        if row["status"] not in {"queued", "running"}:
            return row
        time.sleep(0.01)
    pytest.fail("Job did not settle")


def test_http_lost_creation_response_replays_and_correlates(client, projects, monkeypatch):
    project = projects[0]
    rt = client.app.state.rt
    key_id, token = rt.auth.create_key(project, "Acquisition", ["browser:interact", "content:read"])
    client.headers["Authorization"] = "Bearer " + token
    calls = []

    async def resolve(_):
        return None

    monkeypatch.setattr(rt.browser, "network_factory", lambda _: SimpleNamespace(resolve=resolve))

    async def navigate(project, body, job, tab_id=None):
        calls.append(job.id)
        return {"tab_id": job.tab_id}

    monkeypatch.setattr(rt.browser, "navigate", navigate)
    payload = {"url": "https://example.org/doc"}
    first = client.post(
        "/v1/projects/universrobot/tabs",
        json=payload,
        headers={"Idempotency-Key": "persist-before-send"},
    )
    assert first.status_code == 202
    accepted = first.json()
    assert accepted["tab_id"] and accepted["client_id"] == key_id
    assert accepted["project"] == "universrobot"
    row = wait_job(client, accepted)
    assert row["tab_id"] == accepted["tab_id"]
    assert row["request_id"] == first.headers["x-request-id"]
    repeated = client.post(
        "/v1/projects/universrobot/tabs",
        json=payload,
        headers={"Idempotency-Key": "persist-before-send"},
    )
    assert repeated.json()["job_id"] == accepted["job_id"]
    assert repeated.json()["tab_id"] == accepted["tab_id"] and len(calls) == 1
    assert token not in repeated.text and token not in json.dumps(row)
    conflict = client.post(
        "/v1/projects/universrobot/tabs",
        json={"url": "https://example.org/other"},
        headers={"Idempotency-Key": "persist-before-send"},
    )
    assert conflict.status_code == 409


async def test_tab_close_owner_enforced(client, projects):
    rt = client.app.state.rt
    project = projects[0]
    page = Page()
    closed = []

    async def close():
        closed.append(True)

    page.close = close
    tab = Tab("owned", page, owner_key_id="owner")
    rt.browser.states[project["id"]] = SimpleNamespace(tabs={tab.id: tab}, last_used=0)
    try:
        with pytest.raises(PQError) as error:
            await rt.browser.close_tab(project, tab.id, key_id="other")
        assert error.value.code == "FORBIDDEN" and not closed
        await rt.browser.close_tab(project, tab.id, key_id="owner")
        assert closed == [True]
    finally:
        rt.browser.states.clear()


def test_http_quota_deadline_scope_and_no_creation_retry(client, projects, monkeypatch):
    rt = client.app.state.rt
    _, token = rt.auth.create_key(projects[0], "Low quota", ["browser:interact"], rate_limit=1)
    calls = []

    async def resolve(_):
        return None

    async def navigate(project, body, job, tab_id=None):
        calls.append(job.id)
        return {"tab_id": job.tab_id}

    monkeypatch.setattr(rt.browser, "network_factory", lambda _: SimpleNamespace(resolve=resolve))
    monkeypatch.setattr(rt.browser, "navigate", navigate)
    headers = {"Authorization": "Bearer " + token}
    path = "/v1/projects/universrobot/tabs"
    first = client.post(path, json={"url": "https://example.org/doc"}, headers=headers)
    assert first.status_code == 202
    denied = client.post(path, json={"url": "https://example.org/doc"}, headers=headers)
    assert denied.status_code == 429
    assert int(denied.headers["retry-after"]) > 0
    assert denied.json()["error"]["details"]["scope"] == "api_key"
    assert denied.json()["error"]["details"]["retry_at"] > time.time()
    assert token not in denied.text
    time.sleep(0.03)
    assert len(calls) == 1


async def test_capture_navigation_race_has_no_artifact(client, projects, monkeypatch):
    rt = client.app.state.rt
    project = projects[0]
    page = Page()
    tab = Tab("capture", page)
    tab.evidence = NavigationEvidence(page)

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def operation(*args, **kwargs):
        yield

    tab.audit = SimpleNamespace(operation=operation)
    rt.browser.states[project["id"]] = SimpleNamespace(tabs={tab.id: tab}, last_used=0)

    async def human(*args, **kwargs):
        return None

    async def read(*args, **kwargs):
        tab.evidence.navigated(page.main_frame)
        return "untrusted mixed capture"

    monkeypatch.setattr(rt.browser, "human_guard", human)

    async def no_challenge(*args, **kwargs):
        return False

    monkeypatch.setattr("pagequay.browser.challenge_detected", no_challenge)
    monkeypatch.setattr("pagequay.browser.read_page", read)
    job = SimpleNamespace(set_tab=lambda _: None, request_id="r", id="j")
    try:
        with pytest.raises(PQError) as error:
            await rt.browser.extract(project, tab.id, "text", job, expected_url=page.url)
        assert error.value.code == "NAVIGATION_CHANGED"
        assert not rt.db.all("SELECT * FROM artifacts")
    finally:
        rt.browser.states.clear()


@pytest.mark.parametrize(
    "fault,code",
    [
        (TimeoutError("secret"), "TIMEOUT"),
        (
            PQError("UNAVAILABLE", "secret", 503, details={"cause": "WORLD_NOT_FOUND"}),
            "WORLD_NOT_FOUND",
        ),
        (PQError("INVALID_INPUT", "secret", 413), "SIZE_LIMIT"),
        ("schema", "SCHEMA_REJECTED"),
    ],
)
async def test_child_failure_contains_correlated_bounded_diagnostic(
    monkeypatch, caplog, fault, code
):
    page = Page()
    child = Frame()
    child.parent_frame = page.main_frame
    page.frames.append(child)

    async def visible():
        return True

    async def dispose():
        return None

    async def element():
        async def attribute(name):
            return None

        return SimpleNamespace(is_visible=visible, get_attribute=attribute, dispose=dispose)

    child.frame_element = element

    async def read(*args, frame=None, **kwargs):
        if frame is child:
            if fault == "schema":
                return {}
            raise fault
        return {"blocks": [], "truncated": False}

    monkeypatch.setattr("pagequay.structured.isolated_read", read)
    result = await extract_structured(
        page,
        correlation={
            "request_id": "req-test",
            "job_id": "job-test",
            "tab_id": "tab-test",
            "artifact_id": "artifact-test",
        },
    )
    diagnostic = result["frames"][0]["diagnostic"]
    assert diagnostic["cause"] == code
    assert diagnostic["limit_ms"] == 10000 and diagnostic["duration_ms"] >= 0
    assert diagnostic["is_detached"] is False
    assert result["partial"] and result["frames"][0]["reason"] == "frame_detached_or_unresponsive"
    assert '"frame_id":"f1"' in caplog.text
    assert "artifact-test" in caplog.text and "req-test" in caplog.text
    assert "secret" not in caplog.text


def test_url_credentials_even_empty_are_rejected():
    for url in ("https://@example.org/", "https://:pass@example.org/", "https://user@example.org/"):
        with pytest.raises(PQError):
            NetworkPolicy(Policy()).parse(url)


def test_http_expected_url_never_widens_to_domain(client, projects, monkeypatch):
    rt = client.app.state.rt
    _, token = rt.auth.create_key(projects[0], "Exact", ["browser:interact"])

    async def resolve(_):
        pytest.fail("Mismatched expected URL must be refused before DNS")

    monkeypatch.setattr(rt.browser, "network_factory", lambda _: SimpleNamespace(resolve=resolve))
    response = client.post(
        "/v1/projects/universrobot/tabs",
        headers={"Authorization": "Bearer " + token},
        json={
            "url": "https://example.org/other?secret=value",
            "expected_url": "https://example.org/doc",
            "allow_redirects": False,
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "URL_MISMATCH"
    assert "secret=value" not in response.text
    assert not rt.db.all("SELECT * FROM jobs")


async def test_context_path_uses_dom_owners_not_attachment_order():
    page = Page()
    child = Frame()
    child.parent_frame = page.main_frame
    page.main_frame.child_frames = [Frame(), Frame(), child]
    page.main_frame.dom_frames = [child]
    session = Session(paths=[[0], []])

    async def connect(target):
        if target is child:
            raise PlaywrightError("This frame does not have a separate CDP session")
        return session

    page.context = SimpleNamespace(new_cdp_session=connect)
    from pagequay.diagnostics import ReadTrace

    trace = ReadTrace(child)
    value = await isolated_read(page, "function() {}", {}, frame=child, max_bytes=1024, trace=trace)
    assert value["blocks"] == []
    assert trace.selection["expected_path"] == [0]
    assert trace.selection["session_type"] == "page"
    assert trace.selection["selected_path"] == [0]


async def test_in_process_child_uses_nearest_oopif_target():
    page = Page()
    parent, child = Frame(), Frame()
    parent.parent_frame = page.main_frame
    child.parent_frame = parent
    page.main_frame.dom_frames = [parent]
    parent.dom_frames = [child]
    session = Session(paths=[[0], [0, 0]])
    targets = []

    async def connect(target):
        targets.append(target)
        if target is child:
            raise PlaywrightError("This frame does not have a separate CDP session")
        if target is page:
            pytest.fail("Descendant belongs to the OOPIF target, not the page")
        return session

    page.context = SimpleNamespace(new_cdp_session=connect)
    from pagequay.diagnostics import ReadTrace

    trace = ReadTrace(child)
    await isolated_read(page, "function() {}", {}, frame=child, max_bytes=1024, trace=trace)
    assert targets == [child, parent]
    assert trace.selection["session_type"] == "ancestor_frame_target"
    assert trace.selection["selected_path"] == [0, 0]


async def test_no_candidates_distinguished_from_path_mismatch(caplog):
    page = Page()
    session = Session()
    session.paths = []

    async def connect(_):
        return session

    page.context = SimpleNamespace(new_cdp_session=connect)
    with pytest.raises(PQError) as error:
        await isolated_read(page, "function() {}", {}, max_bytes=1024)
    selection = error.value.details["context_selection"]
    assert selection["candidate_count"] == 0
    assert selection["failure"] == "no_candidates"
    session.paths = [[1]]
    with pytest.raises(PQError) as error:
        await isolated_read(page, "function() {}", {}, max_bytes=1024)
    assert error.value.details["context_selection"]["failure"] == "path_mismatch"
    assert error.value.details["context_selection"]["observed_paths"] == [[1]]


async def test_frame_slot_inventory_is_bounded_before_session():
    page = Page()
    child = Frame()
    child.parent_frame = page.main_frame
    page.main_frame.dom_frames = [Frame()] * 129

    async def connect(_):
        pytest.fail("Overflow must be rejected before creating a CDP session")

    page.context = SimpleNamespace(new_cdp_session=connect)
    with pytest.raises(PQError, match="inventory exceeds"):
        await isolated_read(page, "function() {}", {}, frame=child, max_bytes=1024)


def test_frame_paths_never_publish_arbitrary_values():
    from pagequay.frame_context import bounded_path

    assert bounded_path([0, 127]) == [0, 127]
    for value in ("Bearer SECRET", ["SECRET"], [True], [128], [0] * 33, {"body": "SECRET"}):
        assert bounded_path(value) is None


def test_cloudflare_signal_survives_request_start_and_same_document_commit():
    page = Page()
    evidence = NavigationEvidence(page)
    req = request(page)
    evidence.request(req)
    evidence.response(
        SimpleNamespace(
            request=req,
            url=page.url,
            status=403,
            headers={"cf-mitigated": "challenge", "content-type": "text/html"},
        )
    )
    evidence.navigated(page.main_frame)
    assert evidence.cf_challenge
    page.url += "#still-challenged"
    page.main_frame.url = page.url
    evidence.navigated(page.main_frame)
    assert evidence.cf_challenge
    new_req = request(page)
    evidence.request(new_req)
    assert evidence.cf_challenge  # currently displayed page has not been replaced
    evidence.response(SimpleNamespace(request=new_req, url=page.url, status=200, headers={}))
    assert evidence.cf_challenge  # headers alone do not replace the displayed DOM
    evidence.navigated(page.main_frame)
    assert not evidence.cf_challenge
