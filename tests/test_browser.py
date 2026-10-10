import asyncio
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest

from pagequay.main import create_app
from pagequay.network import NetworkPolicy
from pagequay.settings import Policy, Settings

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(
        os.environ.get("PQ_BROWSER_TESTS") != "1", reason="Set PQ_BROWSER_TESTS=1 for real Chromium"
    ),
]


@pytest.fixture
def site():
    class Handler(BaseHTTPRequestHandler):
        private_hits = 0

        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path == "/private":
                Handler.private_hits += 1
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/private")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            if self.path.startswith("/set-"):
                self.send_header(
                    "Set-Cookie", "sid=" + self.path[5:] + "; Max-Age=3600; Path=/; SameSite=Lax"
                )
            self.end_headers()
            if self.path == "/challenge":
                html = (
                    "<html><head><title>Challenge fixture</title></head>"
                    '<body data-pq-challenge="true">Verify you are human</body></html>'
                )
            else:
                html = f"""<!doctype html><html><head><title>Fixture page</title>
                <meta name="description" content="Local fixture"></head>
                <body><h1 id="rendered">Initial HTML</h1><input id="field">
                <button id="details"
                onclick="document.querySelector('#output').textContent='Clicked'">Details</button>
                <article id="output"></article>
                <a href="https://example.org/article">Example</a><p id="network"></p>
                <script>document.querySelector('#rendered').textContent='Rendered DOM';
                fetch('http://127.0.0.1:{self.server.server_port}/private')
                .then(()=>document.querySelector('#network').textContent='UNSAFE')
                .catch(()=>document.querySelector('#network').textContent='blocked');
                </script></body></html>"""
            self.wfile.write(html.encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_port, Handler
    server.shutdown()
    server.server_close()
    thread.join()


async def poll(client, slug, job_id, headers, expected="completed"):
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        response = await client.get(f"/v1/projects/{slug}/jobs/{job_id}", headers=headers)
        assert response.status_code == 200, response.text
        row = response.json()
        if row["status"] == expected:
            return row
        if row["status"] in {"failed", "cancelled"}:
            pytest.fail(json.dumps(row))
        await asyncio.sleep(0.25)
    pytest.fail("Job polling timed out")


async def test_real_two_profiles_api_retention_challenge_and_crash(tmp_path, site):
    port, handler = site

    def factory(policy):
        return NetworkPolicy(policy, test_allowed_hosts={"localhost"}, test_ports={port})

    settings = Settings(
        data_dir=tmp_path,
        policy=Policy(headless=os.environ.get("PQ_TEST_HEADED") != "1", per_key_rate_limit=600),
        allowed_hosts=["testserver"],
    )
    app = create_app(settings, network_factory=factory)
    async with app.router.lifespan_context(app):
        rt = app.state.rt
        a = rt.db.create_project("universrobot", "UniversRobot")
        b = rt.db.create_project("projet-b", "Projet B")
        scopes = ["browser:read", "browser:interact", "content:read", "screenshot:read"]
        _, ta = rt.auth.create_key(a, "A", scopes, rate_limit=600)
        _, tb = rt.auth.create_key(b, "B", scopes, rate_limit=600)
        ha, hb = {"Authorization": "Bearer " + ta}, {"Authorization": "Bearer " + tb}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 1234)),
            base_url="http://testserver",
        ) as client:

            async def navigate(slug, path, headers):
                response = await client.post(
                    f"/v1/projects/{slug}/tabs",
                    json={"url": f"http://localhost:{port}" + path},
                    headers=headers,
                )
                assert response.status_code == 202, response.text
                return await poll(client, slug, response.json()["job_id"], headers)

            ja, jb = await asyncio.gather(
                navigate("universrobot", "/set-A", ha), navigate("projet-b", "/set-B", hb)
            )
            aid, bid = ja["result"]["tab_id"], jb["result"]["tab_id"]
            assert aid != bid
            assert len(rt.browser.states) == 2
            sa, sb = rt.browser.states[a["id"]], rt.browser.states[b["id"]]
            assert rt.db.project("universrobot")["last_activity"] > a["created_at"]
            assert sa.context is not sb.context
            assert (tmp_path / "profiles" / a["id"]).is_dir() and (
                tmp_path / "profiles" / b["id"]
            ).is_dir()
            assert [c["value"] for c in await sa.context.cookies() if c["name"] == "sid"] == ["A"]
            assert [c["value"] for c in await sb.context.cookies() if c["name"] == "sid"] == ["B"]
            assert await rt.browser.start(a) is sa
            assert (
                await client.get(f"/v1/projects/projet-b/tabs/{aid}", headers=hb)
            ).status_code == 404
            assert await rt.browser.tab(a, aid).page.locator("#network").inner_text() == "blocked"
            assert handler.private_hits == 0
            for format in ("html", "text", "links", "metadata"):
                response = await client.get(
                    f"/v1/projects/universrobot/tabs/{aid}/content?format={format}", headers=ha
                )
                row = await poll(client, "universrobot", response.json()["job_id"], ha)
                artifact = await client.get(row["result"]["url"], headers=ha)
                assert artifact.status_code == 200
                if format in {"html", "text"}:
                    assert b"Rendered DOM" in artifact.content
                elif format == "metadata":
                    assert artifact.json()["title"] == "Fixture page"
                else:
                    assert artifact.json()[0]["url"] == "https://example.org/article"
            response = await client.get(
                f"/v1/projects/universrobot/tabs/{aid}/screenshot", headers=ha
            )
            row = await poll(client, "universrobot", response.json()["job_id"], ha)
            assert (await client.get(row["result"]["url"], headers=ha)).content.startswith(
                b"\x89PNG"
            )
            response = await client.post(
                f"/v1/projects/universrobot/tabs/{aid}/actions",
                headers=ha,
                json={
                    "actions": [
                        {"type": "fill", "selector": "#field", "value": "Test"},
                        {"type": "click", "selector": "#details"},
                    ]
                },
            )
            await poll(client, "universrobot", response.json()["job_id"], ha)
            assert await rt.browser.tab(a, aid).page.locator("#output").inner_text() == "Clicked"
            response = await client.post(
                f"/v1/projects/universrobot/tabs/{aid}/navigate",
                headers=ha,
                json={"url": f"http://localhost:{port}/redirect"},
            )
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                row = (await client.get(response.json()["url"], headers=ha)).json()
                if row["status"] == "failed":
                    break
                await asyncio.sleep(0.1)
            assert row["error"]["code"] == "NAVIGATION_BLOCKED", row
            assert handler.private_hits == 0
            response = await client.post(
                f"/v1/projects/universrobot/tabs/{aid}/navigate",
                headers=ha,
                json={"url": f"http://localhost:{port}/challenge"},
            )
            challenge_id = response.json()["job_id"]
            await poll(client, "universrobot", challenge_id, ha, "waiting_for_human")
            # Simulate human intervention in the test-owned page; no production evaluate route.
            await rt.browser.tab(a, aid).page.evaluate(
                "document.body.removeAttribute('data-pq-challenge');"
                "document.body.textContent='Human completed fixture'"
            )
            assert (
                await client.post(
                    f"/v1/projects/universrobot/jobs/{challenge_id}/resume", headers=ha
                )
            ).status_code == 200
            await poll(client, "universrobot", challenge_id, ha)
            await asyncio.sleep(0.1)
            rt.db.execute("UPDATE artifacts SET expires_at=0")
            await rt.retention.sweep()
            assert rt.db.one("SELECT COUNT(*) AS n FROM artifacts")["n"] == 0
            assert (await sa.context.cookies())[0]["value"] == "A"
            await rt.browser.restart(a)
            sa = rt.browser.states[a["id"]]
            assert [c["value"] for c in await sa.context.cookies() if c["name"] == "sid"] == ["A"]
            # Unexpected closure simulates a browser process disappearing.
            await sa.context.close()
            await asyncio.sleep(0.1)
            assert a["id"] not in rt.browser.states and b["id"] in rt.browser.states
            assert (await sb.context.cookies())[0]["value"] == "B"
            await rt.browser.reset(a)
            sa = await rt.browser.start(a)
            assert not await sa.context.cookies()
            assert (await sb.context.cookies())[0]["value"] == "B"
            sb.last_used = time.time() - 4000
            await rt.retention.sweep()
            assert b["id"] not in rt.browser.states
            sb = await rt.browser.start(b)
            assert (await sb.context.cookies())[0]["value"] == "B"
