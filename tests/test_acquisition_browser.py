import asyncio
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
from playwright.async_api import Error as PlaywrightError

from pagequay.main import create_app
from pagequay.navigation import redirect_guard
from pagequay.network import NetworkPolicy
from pagequay.settings import Policy, Settings

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(os.environ.get("PQ_BROWSER_TESTS") != "1", reason="Use --browser"),
]


@pytest.fixture
async def acquisition_site(tmp_path):
    hits = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            hits.append((self.path, self.headers.get("User-Agent")))
            if self.path == "/slash":
                self.send_response(302)
                self.send_header("Location", "/slash/")
                self.end_headers()
                return
            if self.path == "/private-redirect":
                self.send_response(302)
                self.send_header("Location", "http://10.0.0.1/private")
                self.end_headers()
                return
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "/target?secret=value")
                self.end_headers()
                return
            if self.path == "/cross-host":
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/target")
                self.end_headers()
                return
            self.send_response(404 if self.path == "/404" else 200)
            self.send_header(
                "Content-Type", "text/plain" if self.path == "/robots.txt" else "text/html"
            )
            if self.path == "/cloudflare-custom":
                self.send_header("cf-mitigated", "challenge")
            self.end_headers()
            html = {
                "/rewrite/": (
                    "<title>History rewrite</title><main>Content</main>"
                    "<script>history.replaceState({}, '', '/rewrite')</script>"
                ),
                "/same-history": (
                    "<title>Same URL history</title><main>Content</main>"
                    "<script>history.replaceState({}, '', location.href)</script>"
                ),
                "/robots.txt": (
                    "User-agent: PageQuay\nDisallow: /allowed\n\n"
                    "User-agent: Mozilla\nDisallow: /denied\nAllow: /allowed\n"
                ),
                "/automatic": (
                    "<title>Just a moment</title><p>Checking your browser</p><script>"
                    "setTimeout(()=>{document.title='Ready';document.body.innerHTML="
                    "'<main><p>Resolved content</p></main>';},750)</script>"
                ),
                "/automatic-redirect": (
                    "<title>Just a moment</title><p>Checking your browser</p><script>"
                    "setTimeout(()=>location.href='/allowed',750)</script>"
                ),
                "/cloudflare-custom": "<title>Protection</title><p>Contrôle personnalisé</p>",
                "/automatic-stuck": "<title>Just a moment</title><p>Checking your browser</p>",
                "/captcha": "<title>Just a moment</title><p>Verify you are human</p>",
                "/dom-error": "<title>Error</title><h1>Error 500</h1>",
                "/404": "<h1>Not found</h1>",
                "/oopif": f'<iframe src="http://127.0.0.1:{self.server.server_port}/child#x"></iframe>',
                "/path-mismatch": (
                    "<body><h1>Attachment order differs</h1><script>"
                    "for(let i=0;i<2;i++){const f=document.createElement('iframe');"
                    f"f.src='http://127.0.0.1:{self.server.server_port}/empty';"
                    "f.hidden=true;document.body.append(f);}"
                    "const target=document.createElement('iframe');"
                    "target.id='target';target.src='/child';document.body.prepend(target);"
                    "</script></body>"
                ),
                "/nested-oopif": f'<iframe src="http://127.0.0.1:{self.server.server_port}/nested-child"></iframe>',
                "/nested-child": '<h1>OOPIF parent</h1><iframe src="/child"></iframe>',
                "/large-owner-dom": "<div hidden>"
                + "<span></span>" * 3000
                + '</div><iframe src="/child"></iframe>',
                "/child": "<h2>Other site frame</h2>",
            }.get(self.path, "<title>Fixture</title><main><p>Content</p></main>")
            self.wfile.write(html.encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def network(policy):
        return NetworkPolicy(
            policy, test_allowed_hosts={"localhost", "127.0.0.1"}, test_ports={server.server_port}
        )

    app = create_app(
        Settings(data_dir=tmp_path, allowed_hosts=["testserver"], policy=Policy(headless=True)),
        network_factory=network,
    )
    try:
        async with app.router.lifespan_context(app):
            rt = app.state.rt
            project = rt.db.create_project("acquisition", "Acquisition")
            key_id, token = rt.auth.create_key(
                project, "Fixture", ["browser:read", "browser:interact", "content:read"]
            )
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
                headers={"Authorization": "Bearer " + token},
            ) as client:
                yield rt, project, client, f"http://localhost:{server.server_port}", hits, key_id
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


async def finish(rt, client, response):
    assert response.status_code == 202, response.text
    accepted = response.json()
    await asyncio.wait_for(rt.jobs.active[accepted["job_id"]].task, 30)
    return (await client.get(accepted["url"])).json()


@pytest.mark.parametrize("path,status", [("/allowed", 200), ("/404", 404), ("/dom-error", 200)])
async def test_real_http_status_content_type_and_xpath(acquisition_site, path, status):
    rt, project, client, base, hits, _ = acquisition_site
    prefix = "/v1/projects/acquisition"
    row = await finish(rt, client, await client.post(prefix + "/tabs", json={"url": base + path}))
    assert row["status"] == "completed", row
    tab_id = row["tab_id"]
    proof = row["result"]["navigation"]
    assert proof["http_status"] == status
    assert proof["requested_url"] == proof["final_url"] == base + path
    assert proof["content_type"] == "text/html"
    result = await finish(
        rt,
        client,
        await client.get(
            prefix + f"/tabs/{tab_id}/content",
            params={"format": "structured", "expected_url": base + path},
        ),
    )
    assert result["status"] == "completed", result
    artifact = await client.get(result["result"]["url"])
    data = artifact.json()
    assert data["navigation"] == proof and artifact.headers["content-type"] == "application/json"
    assert data["artifact_id"] == result["result"]["artifact_id"]
    page = rt.browser.tab(project, tab_id).page
    for block in data["blocks"]:
        xpath = block["provenance"]["xpath"]
        assert xpath and await page.locator("xpath=" + xpath).count() == 1
    assert hits and all(ua.startswith("Mozilla/5.0 ") and "Chrome/" in ua for _, ua in hits)


@pytest.mark.parametrize("path", ["/redirect", "/cross-host"])
async def test_real_redirect_target_never_requested(acquisition_site, path):
    rt, project, _, base, hits, _ = acquisition_site
    tab = await rt.browser.new_tab(project)
    url = base + path
    network = rt.browser.network_factory(rt.db.policy(project))
    async with redirect_guard(tab.page, network, expected_url=url, allow_redirects=False) as errors:
        with pytest.raises(PlaywrightError):
            await tab.page.goto(url, timeout=5000)
        assert errors and errors[0].code == "REDIRECT_BLOCKED"
    assert not any(path.startswith("/target") for path, _ in hits)


async def test_robots_denied_before_document_and_helper_cleanup(acquisition_site):
    rt, project, client, base, hits, _ = acquisition_site
    response = await client.post(
        "/v1/projects/acquisition/tabs", json={"url": base + "/denied", "respect_robots": True}
    )
    row = await finish(rt, client, response)
    assert row["error"]["code"] == "ROBOTS_DENIED", row
    assert not any(path == "/denied" for path, _ in hits)
    assert len(rt.browser.list_tabs(project)) == 1  # acquisition tab kept; helper closed
    row = await finish(
        rt,
        client,
        await client.post(
            "/v1/projects/acquisition/tabs", json={"url": base + "/allowed", "respect_robots": True}
        ),
    )
    assert row["status"] == "completed", row
    assert row["result"]["robots"]["allowed"] is True
    robots_agents = {ua for path, ua in hits if path == "/robots.txt"}
    assert robots_agents == {row["result"]["robots"]["user_agent"]}
    assert row["result"]["robots"]["user_agent"].startswith("Mozilla/5.0 ")
    assert len(rt.browser.list_tabs(project)) == 2


async def test_same_url_navigation_during_extract_rejects_artifact(acquisition_site, monkeypatch):
    rt, _, client, base, _, _ = acquisition_site
    prefix = "/v1/projects/acquisition"
    row = await finish(
        rt, client, await client.post(prefix + "/tabs", json={"url": base + "/allowed"})
    )
    original = __import__("pagequay.browser", fromlist=["extract_structured"]).extract_structured

    async def racing(page, **kwargs):
        value = await original(page, **kwargs)
        await page.reload()
        return value

    monkeypatch.setattr("pagequay.browser.extract_structured", racing)
    row = await finish(
        rt,
        client,
        await client.get(
            prefix + f"/tabs/{row['tab_id']}/content",
            params={"format": "structured", "expected_url": base + "/allowed"},
        ),
    )
    assert row["error"]["code"] == "NAVIGATION_CHANGED", row
    assert not rt.db.all("SELECT * FROM artifacts")


async def test_oopif_frame_path_and_isolated_world(acquisition_site):
    rt, _, client, base, _, _ = acquisition_site
    prefix = "/v1/projects/acquisition"
    row = await finish(
        rt,
        client,
        await client.post(prefix + "/tabs", json={"url": base + "/oopif", "wait_until": "load"}),
    )
    row = await finish(
        rt,
        client,
        await client.get(
            prefix + f"/tabs/{row['tab_id']}/content", params={"format": "structured"}
        ),
    )
    assert row["status"] == "completed", row
    data = (await client.get(row["result"]["url"])).json()
    assert data["frames"][0]["status"] == "extracted", data["frames"]
    assert "Other site frame" in str(data["frames"][0]["document"]["blocks"])


async def test_captcha_remains_human_wait_and_cancel_preserves_tab(acquisition_site):
    rt, project, client, base, _, key_id = acquisition_site
    accepted = (
        await client.post("/v1/projects/acquisition/tabs", json={"url": base + "/captcha"})
    ).json()
    job = rt.jobs.active[accepted["job_id"]]
    for _ in range(100):
        if job.status == "waiting_for_human":
            break
        await asyncio.sleep(0.05)
    assert job.status == "waiting_for_human"
    assert rt.jobs.get(project, job.id)["tab_id"] == accepted["tab_id"]
    tab = rt.browser.tab(project, accepted["tab_id"])
    assert (
        tab.evidence.snapshot()["http_status"] == 200
    )  # actual response, not inferred CAPTCHA status
    assert (await client.post(accepted["url"] + "/cancel")).status_code == 200
    await job.task
    assert rt.jobs.get(project, job.id)["status"] == "cancelled"
    assert not tab.page.is_closed()
    await rt.browser.close_tab(project, tab.id, key_id=key_id)
    assert not rt.browser.list_tabs(project)


async def test_legacy_redirect_chain_is_main_document_evidence(acquisition_site):
    rt, _, client, base, hits, _ = acquisition_site
    row = await finish(
        rt,
        client,
        await client.post(
            "/v1/projects/acquisition/tabs",
            json={"url": base + "/redirect", "allow_redirects": True},
        ),
    )
    assert row["status"] == "completed", row
    proof = row["result"]["navigation"]
    assert proof["requested_url"] == base + "/redirect"
    assert proof["final_url"] == base + "/target?secret=value"
    assert proof["redirect_chain"][0]["http_status"] == 302
    assert proof["http_status"] == 200
    assert any(path.startswith("/target") for path, _ in hits)


async def test_strict_subframe_refusal_before_child_request(acquisition_site, monkeypatch):
    # Test injection permits this loopback fixture only; production HTTPS validation
    # is covered separately. Real route/egress/CDP behavior remains active.
    rt, project, client, base, hits, _ = acquisition_site
    monkeypatch.setattr("pagequay.api.require_https", lambda _: None)
    monkeypatch.setattr("pagequay.browser.require_https", lambda _: None)
    monkeypatch.setattr("pagequay.navigation.require_https", lambda _: None)
    row = await finish(
        rt,
        client,
        await client.post(
            "/v1/projects/acquisition/tabs",
            json={
                "url": base + "/oopif",
                "expected_url": base + "/oopif",
                "allow_redirects": False,
                "wait_until": "load",
            },
        ),
    )
    assert row["status"] == "completed", row
    assert not any(path == "/child" for path, _ in hits)
    refusals = row["result"]["network_policy"]["refusals"]
    assert any(r["cause"] == "strict_subframe_network_unattested" for r in refusals)
    result = await finish(
        rt,
        client,
        await client.get(
            f"/v1/projects/acquisition/tabs/{row['tab_id']}/content?format=structured"
        ),
    )
    data = (await client.get(result["result"]["url"])).json()
    assert data["partial"]
    assert data["network_policy"]["subframe_network"] == "denied"


async def test_error_dom_without_http_response_stays_unknown(acquisition_site):
    rt, project, client, _, _, _ = acquisition_site
    tab = await rt.browser.new_tab(project)
    await tab.page.set_content("<title>HTTP 500 error</title><h1>Server error</h1>")
    row = await finish(
        rt,
        client,
        await client.get(f"/v1/projects/acquisition/tabs/{tab.id}/content?format=structured"),
    )
    assert row["status"] == "completed", row
    data = (await client.get(row["result"]["url"])).json()
    assert data["navigation"]["http_status"] is None
    assert data["navigation"]["content_type"] is None
    assert data["navigation"]["http_status_reason"] == "no_main_document_response_observed"


async def test_human_timeout_preserves_capture_navigation_and_owned_tab(
    acquisition_site, monkeypatch
):
    rt, project, client, base, _, key_id = acquisition_site
    monkeypatch.setattr(rt.settings, "human_timeout_seconds", 0.03)
    row = await finish(
        rt,
        client,
        await client.post("/v1/projects/acquisition/tabs", json={"url": base + "/captcha"}),
    )
    assert row["status"] == "failed" and row["error"]["code"] == "TIMEOUT", row
    assert row["result"]["navigation"]["http_status"] == 200
    assert row["result"]["capture"]["media_type"] == "image/png"
    tab = rt.browser.tab(project, row["tab_id"])
    assert not tab.page.is_closed()
    await rt.browser.close_tab(project, tab.id, key_id=key_id)


async def test_frame_owner_mapping_handles_dom_vs_native_window_order(acquisition_site):
    rt, project, client, base, _, _ = acquisition_site
    prefix = "/v1/projects/acquisition"
    row = await finish(
        rt,
        client,
        await client.post(
            prefix + "/tabs", json={"url": base + "/path-mismatch", "wait_until": "load"}
        ),
    )
    page = rt.browser.tab(project, row["tab_id"]).page
    owner = await page.locator("#target").element_handle()
    target = await owner.content_frame()
    await owner.dispose()
    assert page.main_frame.child_frames.index(target) == 2
    # Hostile authored JS cannot alter the utility-world identity probe.
    await page.evaluate("""() => {
        document.createTreeWalker = () => { throw new Error('PAGE SECRET'); };
        Object.defineProperty(document.querySelector('#target'), 'contentWindow', {
            get() { return null; }
        });
    }""")
    row = await finish(
        rt, client, await client.get(prefix + f"/tabs/{row['tab_id']}/content?format=structured")
    )
    data = (await client.get(row["result"]["url"])).json()
    assert not data["partial"] and not data["truncated"]
    visible = next(frame for frame in data["frames"] if frame["status"] == "extracted")
    assert "Other site frame" in str(visible["document"]["blocks"])
    selection = visible["context_selection"]
    assert selection["session_type"] == "page"
    assert selection["expected_path"] == selection["selected_path"] == [2]
    assert [2] in selection["observed_paths"]


async def test_in_process_descendant_of_oopif_uses_ancestor_target(acquisition_site):
    rt, _, client, base, _, _ = acquisition_site
    prefix = "/v1/projects/acquisition"
    row = await finish(
        rt,
        client,
        await client.post(
            prefix + "/tabs", json={"url": base + "/nested-oopif", "wait_until": "load"}
        ),
    )
    row = await finish(
        rt, client, await client.get(prefix + f"/tabs/{row['tab_id']}/content?format=structured")
    )
    data = (await client.get(row["result"]["url"])).json()
    assert not data["partial"], data["frames"]
    nested = next(frame for frame in data["frames"] if frame["parent_frame_id"] != "f0")
    assert nested["status"] == "extracted"
    assert "Other site frame" in str(nested["document"]["blocks"])
    assert nested["context_selection"]["session_type"] == "ancestor_frame_target"
    assert nested["context_selection"]["selected_path"] == [0, 0]


async def test_unrelated_hidden_dom_does_not_consume_frame_owner_budget(acquisition_site):
    rt, _, client, base, _, _ = acquisition_site
    prefix = "/v1/projects/acquisition"
    row = await finish(
        rt,
        client,
        await client.post(
            prefix + "/tabs", json={"url": base + "/large-owner-dom", "wait_until": "load"}
        ),
    )
    row = await finish(
        rt, client, await client.get(prefix + f"/tabs/{row['tab_id']}/content?format=structured")
    )
    data = (await client.get(row["result"]["url"])).json()
    assert not data["partial"] and not data["truncated"], data["frames"]
    assert "Other site frame" in str(data["frames"][0]["document"]["blocks"])


def permit_fixture_https(monkeypatch):
    # Only the local injected fixture; production HTTPS/ports remain unchanged.
    for module in ("api", "browser", "navigation"):
        monkeypatch.setattr(f"pagequay.{module}.require_https", lambda _: None)


async def wait_human(job):
    for _ in range(160):
        if job.status == "waiting_for_human":
            return
        assert job.status in {"queued", "running"}, job.status
        await asyncio.sleep(0.05)
    pytest.fail("Job did not enter waiting_for_human")


@pytest.mark.parametrize("path", ["/automatic", "/automatic-redirect"])
async def test_automatic_verification_then_final_scope(acquisition_site, monkeypatch, path):
    rt, project, client, base, _, _ = acquisition_site
    permit_fixture_https(monkeypatch)
    prefix = "/v1/projects/acquisition"
    expected = base + ("/allowed" if path.endswith("redirect") else path)
    row = await finish(
        rt,
        client,
        await client.post(
            prefix + "/tabs",
            json={
                "url": base + path,
                "expected_url": expected,
            },
        ),
    )
    assert row["status"] == "completed", row
    assert row["result"]["navigation"]["final_url"] == expected
    assert row["result"]["title"] != "Just a moment"
    assert not rt.db.all("SELECT * FROM artifacts")  # no automatic challenge screenshot
    extracted = await finish(
        rt,
        client,
        await client.get(
            prefix + f"/tabs/{row['tab_id']}/content",
            params={"format": "structured"},
        ),
    )
    assert extracted["status"] == "completed", extracted
    data = (await client.get(extracted["result"]["url"])).json()
    assert not data["partial"]
    assert "Checking your browser" not in str(data["blocks"])


async def test_scope_changed_never_transfers_approval(acquisition_site, monkeypatch):
    rt, _, client, base, hits, _ = acquisition_site
    permit_fixture_https(monkeypatch)
    prefix = "/v1/projects/acquisition"
    row = await finish(
        rt,
        client,
        await client.post(
            prefix + "/tabs",
            json={
                "url": base + "/redirect",
                "expected_url": base + "/redirect",
                "respect_robots": True,
            },
        ),
    )
    assert any(path.startswith("/target") for path, _ in hits)  # robots didn't force False
    assert row["status"] == "failed"
    assert row["error"]["code"] == "scope_changed"
    details = row["error"]["details"]
    assert details["target_url"] == base + "/target"
    assert details["navigation"]["final_url"] == base + "/target?secret=value"

    async def forbidden(*args, **kwargs):
        pytest.fail("Business extraction must not run outside the approved scope")

    monkeypatch.setattr("pagequay.browser.extract_structured", forbidden)
    # Omission of expected_url cannot adopt the changed navigation target.
    extracted = await finish(
        rt,
        client,
        await client.get(
            prefix + f"/tabs/{row['tab_id']}/content",
            params={"format": "structured"},
        ),
    )
    assert extracted["error"]["code"] == "scope_changed", extracted
    assert not rt.db.all("SELECT * FROM artifacts")


@pytest.mark.parametrize("kind", ["navigate", "content"])
@pytest.mark.parametrize("human_target", ["/allowed", "/other"])
async def test_human_resume_checks_new_document_before_capture(
    acquisition_site,
    monkeypatch,
    kind,
    human_target,
):
    rt, project, client, base, _, _ = acquisition_site
    permit_fixture_https(monkeypatch)
    prefix = "/v1/projects/acquisition"
    if kind == "navigate":
        response = await client.post(
            prefix + "/tabs",
            json={
                "url": base + "/captcha",
                "expected_url": base + "/allowed",
            },
        )
    else:
        tab = await rt.browser.new_tab(project)
        await tab.page.goto(base + "/captcha")
        response = await client.get(
            prefix + f"/tabs/{tab.id}/content",
            params={
                "format": "structured",
                "expected_url": base + "/allowed",
            },
        )
    assert response.status_code == 202
    accepted = response.json()
    job = rt.jobs.active[accepted["job_id"]]
    await wait_human(job)
    assert all(row["media_type"] == "image/png" for row in rt.db.all("SELECT * FROM artifacts"))
    tab = rt.browser.tab(project, accepted["tab_id"])
    # Simulate the human operating their browser, independently of the API lock.
    await tab.page.goto(base + human_target)
    assert (await client.post(accepted["url"] + "/resume")).status_code == 200
    row = await finish(rt, client, response)
    if human_target != "/allowed":
        assert row["error"]["code"] == "scope_changed", row
        assert all(r["media_type"] == "image/png" for r in rt.db.all("SELECT * FROM artifacts"))
        return
    assert row["status"] == "completed", row
    assert row["result"]["navigation"]["final_url"] == base + "/allowed"
    if kind == "content":
        data = (await client.get(row["result"]["url"])).json()
        assert "Verify you are human" not in str(data["blocks"])


async def test_automatic_wait_exhaustion_and_unresolved_resume(acquisition_site):
    rt, project, client, base, _, _ = acquisition_site
    rt.db.execute(
        "UPDATE projects SET config=? WHERE id=?",
        (
            '{"navigation_timeout_seconds":1}',
            project["id"],
        ),
    )
    accepted = (
        await client.post(
            "/v1/projects/acquisition/tabs",
            json={
                "url": base + "/automatic-stuck",
            },
        )
    ).json()
    job = rt.jobs.active[accepted["job_id"]]
    await wait_human(job)
    assert (await client.post(accepted["url"] + "/resume")).status_code == 200
    await asyncio.sleep(0.4)
    await wait_human(job)
    assert all(row["media_type"] == "image/png" for row in rt.db.all("SELECT * FROM artifacts"))
    await client.post(accepted["url"] + "/cancel")
    await job.task


@pytest.mark.parametrize("invalidate_inside_reader", [False, True])
async def test_challenge_appearing_during_capture_discards_snapshot(
    acquisition_site,
    monkeypatch,
    invalidate_inside_reader,
):
    rt, project, client, base, _, _ = acquisition_site
    prefix = "/v1/projects/acquisition"
    row = await finish(
        rt, client, await client.post(prefix + "/tabs", json={"url": base + "/allowed"})
    )
    original = __import__("pagequay.browser", fromlist=["extract_structured"]).extract_structured
    first = True

    async def racing(page, **kwargs):
        nonlocal first
        value = await original(page, **kwargs)
        if first:
            first = False
            await page.goto(base + "/captcha")
            if invalidate_inside_reader:
                kwargs["check"]()
        return value

    monkeypatch.setattr("pagequay.browser.extract_structured", racing)
    response = await client.get(
        prefix + f"/tabs/{row['tab_id']}/content",
        params={
            "format": "structured",
            "expected_url": base + "/allowed",
        },
    )
    accepted = response.json()
    job = rt.jobs.active[accepted["job_id"]]
    await wait_human(job)
    assert all(row["media_type"] == "image/png" for row in rt.db.all("SELECT * FROM artifacts"))
    await rt.browser.tab(project, row["tab_id"]).page.goto(base + "/allowed")
    await client.post(accepted["url"] + "/resume")
    result = await finish(rt, client, response)
    assert result["status"] == "completed", result
    assert len(rt.db.all("SELECT * FROM artifacts WHERE media_type='application/json'")) == 1


async def test_allowed_redirect_still_rejects_private_network(acquisition_site):
    rt, _, client, base, _, _ = acquisition_site
    row = await finish(
        rt,
        client,
        await client.post(
            "/v1/projects/acquisition/tabs",
            json={
                "url": base + "/private-redirect",
                "allow_redirects": True,
            },
        ),
    )
    assert row["status"] == "failed", row
    assert row["error"]["code"] == "NAVIGATION_BLOCKED", row


async def test_custom_cloudflare_header_prevents_business_capture(acquisition_site):
    rt, project, client, base, _, _ = acquisition_site
    rt.db.execute(
        "UPDATE projects SET config=? WHERE id=?",
        (
            '{"navigation_timeout_seconds":1}',
            project["id"],
        ),
    )
    tab = await rt.browser.new_tab(project)
    await tab.page.goto(base + "/cloudflare-custom")
    assert tab.evidence.cf_challenge
    await tab.page.goto(base + "/cloudflare-custom#still-challenged")
    assert tab.evidence.cf_challenge  # hash/history must not erase the response signal
    response = await client.get(
        f"/v1/projects/acquisition/tabs/{tab.id}/content",
        params={
            "format": "structured",
            "expected_url": base + "/allowed",
        },
    )
    accepted = response.json()
    job = rt.jobs.active[accepted["job_id"]]
    await wait_human(job)
    assert all(row["media_type"] == "image/png" for row in rt.db.all("SELECT * FROM artifacts"))
    await tab.page.goto(base + "/allowed")
    assert not tab.evidence.cf_challenge
    await client.post(accepted["url"] + "/resume")
    row = await finish(rt, client, response)
    assert row["status"] == "completed", row


@pytest.mark.parametrize("path,destination", [("/slash", "/slash/"), ("/rewrite/", "/rewrite")])
async def test_exact_slash_mismatch_has_stage_and_preserved_response(
    acquisition_site, monkeypatch, path, destination
):
    rt, project, client, base, _, _ = acquisition_site
    permit_fixture_https(monkeypatch)
    prefix = "/v1/projects/acquisition"
    row = await finish(
        rt,
        client,
        await client.post(prefix + "/tabs", json={"url": base + path, "expected_url": base + path}),
    )
    assert row["error"]["code"] == "scope_changed", row
    details = row["error"]["details"]
    assert details["expected_url"] == base + path
    assert details["observed_url"] == base + destination
    assert details["stage"] == "navigation.after_wait"
    assert details["job_id"] == row["id"]
    assert details["tab_id"] == row["tab_id"]
    assert details["request_id"] == row["request_id"]
    assert details["observed_at"].endswith("+00:00")
    assert details["artifact_id"] is None and not details["artifact_published"]
    proof = details["navigation"]
    response_url = base + (destination if path == "/slash" else path)
    assert proof["main_document_response"]["url"] == response_url
    assert proof["main_document_response"]["http_status"] == 200
    if path == "/slash":
        assert proof["redirect_chain"][0]["http_status"] == 302
    else:
        assert not proof["redirect_chain"]
        assert proof["url_changes"][-1]["to_url"] == base + destination
        assert proof["same_document_navigations"][-1] == {
            "url": base + destination,
            "navigation_type": "historyApi",
            "observed_at": proof["same_document_navigations"][-1]["observed_at"],
        }
    for fmt in ("structured", "html"):
        export = await finish(
            rt,
            client,
            await client.get(prefix + f"/tabs/{row['tab_id']}/content", params={"format": fmt}),
        )
        assert export["error"]["code"] == "scope_changed"
        d = export["error"]["details"]
        assert d["stage"] == f"export.{fmt}.before_capture"
        assert d["expected_url"] == base + path
        assert d["observed_url"] == base + destination
    assert not rt.db.all("SELECT * FROM artifacts")


@pytest.mark.parametrize("path", ["/slash/", "/same-history", "/long?" + "x" * 2200])
async def test_tab_structured_html_metadata_use_same_exact_url(acquisition_site, path):
    rt, _, client, base, _, _ = acquisition_site
    prefix = "/v1/projects/acquisition"
    row = await finish(rt, client, await client.post(prefix + "/tabs", json={"url": base + path}))
    assert row["status"] == "completed", row
    endpoint = prefix + f"/tabs/{row['tab_id']}"
    info = (await client.get(endpoint)).json()
    assert info["url"] == base + path
    for fmt in ("structured", "html"):
        exported = await finish(
            rt,
            client,
            await client.get(
                endpoint + "/content", params={"format": fmt, "expected_url": base + path}
            ),
        )
        assert exported["status"] == "completed", exported
        assert exported["result"]["navigation"] == info["navigation"]
        assert exported["result"]["navigation"]["main_document_response"]["http_status"] == 200
        artifact = await client.get(exported["result"]["url"])
        if fmt == "structured":
            value = artifact.json()
            assert value["url"] == base + path
            assert value["navigation"] == info["navigation"]
            assert value["schema_version"] == "1.0"
            assert not any(value[k] for k in ("partial", "truncated", "frame_limit_reached"))
        else:
            assert artifact.headers["content-type"].startswith("text/html")
    assert (await client.get(endpoint)).json()["url"] == base + path


@pytest.mark.parametrize("fmt", ["structured", "html"])
@pytest.mark.parametrize("target", ["/allowed/", "/allowed?changed=1", "cross_domain"])
async def test_actual_destination_change_during_export_never_publishes(
    acquisition_site, monkeypatch, fmt, target
):
    rt, _, client, base, _, _ = acquisition_site
    prefix = "/v1/projects/acquisition"
    row = await finish(
        rt, client, await client.post(prefix + "/tabs", json={"url": base + "/allowed"})
    )
    from pagequay import browser

    original = browser.extract_structured if fmt == "structured" else browser.read_page
    destination = (
        base + target
        if target != "cross_domain"
        else base.replace("localhost", "127.0.0.1") + "/allowed"
    )

    async def racing(page, *args, **kwargs):
        value = await original(page, *args, **kwargs)
        if fmt == "html" and args[0] != "html":
            return value
        await page.goto(destination)
        return value

    monkeypatch.setattr(
        browser, "extract_structured" if fmt == "structured" else "read_page", racing
    )
    row = await finish(
        rt,
        client,
        await client.get(
            prefix + f"/tabs/{row['tab_id']}/content",
            params={"format": fmt, "expected_url": base + "/allowed"},
        ),
    )
    assert row["error"]["code"] == "scope_changed", row
    details = row["error"]["details"]
    assert details["observed_url"] == destination
    assert details["expected_url"] == base + "/allowed"
    assert details["stage"] == (
        "export.structured.metadata" if fmt == "structured" else "export.html.before_publish"
    )
    assert details["artifact_id"] and not details["artifact_published"]
    assert not rt.db.all("SELECT * FROM artifacts")


async def test_inconsistent_structured_identity_is_rejected(acquisition_site, monkeypatch):
    rt, _, client, base, _, _ = acquisition_site
    prefix = "/v1/projects/acquisition"
    row = await finish(
        rt, client, await client.post(prefix + "/tabs", json={"url": base + "/allowed"})
    )
    from pagequay import browser

    original = browser.extract_structured

    async def inconsistent(page, **kwargs):
        value = await original(page, **kwargs)
        value["url"] = base + "/other"
        return value

    monkeypatch.setattr(browser, "extract_structured", inconsistent)
    row = await finish(
        rt,
        client,
        await client.get(
            prefix + f"/tabs/{row['tab_id']}/content",
            params={"format": "structured", "expected_url": base + "/allowed"},
        ),
    )
    assert row["error"]["code"] == "URL_METADATA_MISMATCH", row
    assert row["error"]["details"]["stage"] == "export.structured.metadata"
    assert not rt.db.all("SELECT * FROM artifacts")


@pytest.mark.parametrize("format", ["structured", "html"])
async def test_single_same_url_rewrite_recaptures_before_publish(
    acquisition_site, monkeypatch, format
):
    rt, _, client, base, _, _ = acquisition_site
    prefix = "/v1/projects/acquisition"
    row = await finish(
        rt, client, await client.post(prefix + "/tabs", json={"url": base + "/allowed"})
    )
    module = __import__("pagequay.browser", fromlist=["read_page"])
    target = "extract_structured" if format == "structured" else "read_page"
    original = getattr(module, target)
    calls = 0

    async def racing(page, *args, **kwargs):
        nonlocal calls
        if target == "read_page" and args[0] != "html":
            return await original(page, *args, **kwargs)
        calls += 1
        value = await original(page, *args, **kwargs)
        if calls == 1:
            await page.evaluate(
                "document.querySelector('p').textContent='Fresh verified content';"
                "history.replaceState({}, '', location.href)"
            )
            await asyncio.sleep(0.02)
        return value

    monkeypatch.setattr(module, target, racing)
    row = await finish(
        rt,
        client,
        await client.get(
            prefix + f"/tabs/{row['tab_id']}/content",
            params={"format": format, "expected_url": base + "/allowed"},
        ),
    )
    assert row["status"] == "completed", row
    assert calls == 2
    assert len(rt.db.all("SELECT * FROM artifacts")) == 1
    artifact = await client.get(row["result"]["url"])
    assert "Fresh verified content" in artifact.text


@pytest.mark.parametrize("exact_scope", [False, True])
async def test_export_rewrite_to_other_url_never_recaptures(
    acquisition_site, monkeypatch, exact_scope
):
    rt, _, client, base, _, _ = acquisition_site
    prefix = "/v1/projects/acquisition"
    row = await finish(
        rt, client, await client.post(prefix + "/tabs", json={"url": base + "/allowed"})
    )
    module = __import__("pagequay.browser", fromlist=["read_page"])
    original = module.read_page
    calls = 0

    async def racing(page, *args, **kwargs):
        nonlocal calls
        if args[0] != "html":
            return await original(page, *args, **kwargs)
        calls += 1
        value = await original(page, *args, **kwargs)
        await page.evaluate("history.replaceState({}, '', '/other')")
        await asyncio.sleep(0.02)
        return value

    monkeypatch.setattr(module, "read_page", racing)
    row = await finish(
        rt,
        client,
        await client.get(
            prefix + f"/tabs/{row['tab_id']}/content",
            params={
                "format": "html",
                **({"expected_url": base + "/allowed"} if exact_scope else {}),
            },
        ),
    )
    assert row["error"]["code"] == ("scope_changed" if exact_scope else "NAVIGATION_CHANGED"), row
    assert calls == 1 and not rt.db.all("SELECT * FROM artifacts")
