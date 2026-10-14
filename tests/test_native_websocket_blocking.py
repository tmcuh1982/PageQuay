"""Real positive/negative handshakes: the proxy map must cover every execution context."""

import base64
import hashlib
import json
import os
import ssl
import subprocess
from http import HTTPStatus

import pytest
from playwright.async_api import BrowserType, async_playwright
from websockets.asyncio.server import serve

from pagequay.cdp_launch import browser_executable, launch_executable
from pagequay.main import create_app
from pagequay.network import NetworkPolicy
from pagequay.settings import Policy, Settings

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(os.environ.get("PQ_BROWSER_TESTS") != "1", reason="Requires browser"),
]

PROBE = """async urls => ({native: String(WebSocket).includes('[native code]'),
    results: await Promise.all(urls.map(url => new Promise(resolve => {
        const ws = new WebSocket(url);
        const timer = setTimeout(() => resolve('timeout'), 5000);
        ws.onopen = () => { clearTimeout(timer); ws.close(); resolve('open'); };
        ws.onerror = () => { clearTimeout(timer); resolve('error'); };
    })))})"""


@pytest.fixture
def certificate(tmp_path):
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost,IP:127.0.0.1",
        ],
        check=True,
        capture_output=True,
    )
    public = subprocess.check_output(["openssl", "x509", "-in", str(cert), "-pubkey", "-noout"])
    der = subprocess.check_output(["openssl", "pkey", "-pubin", "-outform", "DER"], input=public)
    spki = base64.b64encode(hashlib.sha256(der).digest()).decode()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    return context, spki


@pytest.mark.parametrize("channel", ["chromium", "chrome"])
async def test_native_websockets_blocked_everywhere_and_proxy_failure_stays_closed(
    tmp_path,
    monkeypatch,
    certificate,
    channel,
):
    tls, spki = certificate
    handshakes = []
    urls = []

    async def websocket(connection):
        handshakes.append(connection.request.path)
        await connection.wait_closed()

    async def http(connection, request):
        if request.headers.get("Upgrade", "").lower() == "websocket":
            return None
        script = f"window.resultPromise = ({PROBE})({json.dumps(urls)});"
        html = "<title>Fixture</title>"
        if request.path.startswith("/auto"):
            html += f"<script>{script}</script>"
        response = connection.respond(HTTPStatus.OK, html)
        response.headers["Content-Type"] = "text/html; charset=utf-8"
        return response

    original_launch = BrowserType.launch_persistent_context

    async def launch_with_test_certificate(browser_type, *args, **kwargs):
        # Trust only this test's ephemeral certificate; no production TLS override.
        kwargs["args"] = [*kwargs.get("args", []), f"--ignore-certificate-errors-spki-list={spki}"]
        return await original_launch(browser_type, *args, **kwargs)

    monkeypatch.setattr(BrowserType, "launch_persistent_context", launch_with_test_certificate)
    async with (
        serve(websocket, "127.0.0.1", 0, process_request=http) as plain,
        serve(websocket, "127.0.0.1", 0, process_request=http, ssl=tls) as secure,
    ):
        port, tls_port = plain.sockets[0].getsockname()[1], secure.sockets[0].getsockname()[1]
        http_url = f"http://127.0.0.1:{port}"
        https_url = f"https://127.0.0.1:{tls_port}"
        urls[:] = [f"ws://127.0.0.1:{port}/socket", f"wss://127.0.0.1:{tls_port}/socket"]
        # Positive control: both endpoints really accept connections with this browser.
        async with async_playwright() as pw:
            with launch_executable(tmp_path, browser_executable(pw.chromium, channel)) as launcher:
                control = await pw.chromium.launch_persistent_context(
                    str(tmp_path / "control"),
                    executable_path=launcher,
                    channel=channel,
                    headless=True,
                    chromium_sandbox=True,
                )
            try:
                await control.pages[0].goto(http_url)
                assert await control.pages[0].evaluate(PROBE, urls) == {
                    "native": True,
                    "results": ["open", "open"],
                }
            finally:
                await control.close()
        assert len(handshakes) == 2
        handshakes.clear()

        def factory(policy):
            return NetworkPolicy(
                policy,
                test_allowed_hosts={"127.0.0.1", "localhost"},
                test_ports={port, tls_port},
            )

        settings = Settings(
            data_dir=tmp_path / "guarded",
            browser_channel=channel,
            policy=Policy(headless=True),
        )
        app = create_app(settings, network_factory=factory)
        async with app.router.lifespan_context(app):
            rt = app.state.rt
            project = rt.db.create_project("websocket-test", "WebSocket test")
            tab = await rt.browser.new_tab(project)
            page = tab.page
            state = rt.browser.states[project["id"]]
            expected = {"native": True, "results": ["error", "error"]}
            # Runs during document parsing, before page/frame event handlers could patch JS.
            for origin in (http_url, https_url):
                response = await page.goto(origin + "/auto")
                assert response.status == 200
                assert await page.evaluate("window.resultPromise") == expected
                assert await page.evaluate(
                    "!('__pwWebSocketBinding' in globalThis) && "
                    "!('__pwWebSocketDispatch' in globalThis)"
                )
            await page.goto(http_url)
            # HTTP(S) passed to the constructor is normalized to WS(S), too.
            assert (
                await page.evaluate(PROBE, [http_url + "/socket", https_url + "/socket"])
                == expected
            )
            for src in (http_url + "/auto", f"http://localhost:{port}/auto"):
                async with page.expect_event("frameattached") as frame_info:
                    await page.evaluate(
                        "src => { const f=document.createElement('iframe'); "
                        "f.src=src; document.body.append(f); }",
                        src,
                    )
                frame = await frame_info.value
                await frame.wait_for_url(src)
                assert await frame.evaluate("window.resultPromise") == expected
            await page.evaluate(
                "html => { const f=document.createElement('iframe'); "
                "f.id='srcdoc'; f.srcdoc=html; document.body.append(f); }",
                f"<script>window.resultPromise = ({PROBE})({json.dumps(urls)});</script>",
            )
            frame = await page.locator("#srcdoc").element_handle()
            child = await frame.content_frame()
            await child.wait_for_function("window.resultPromise")
            assert await child.evaluate("window.resultPromise") == expected
            async with page.expect_popup() as popup_info:
                await page.evaluate("window.open('about:blank')")
            popup = await popup_info.value
            await popup.goto(http_url + "/auto")
            assert await popup.evaluate("window.resultPromise") == expected
            await popup.close()
            for shared in (False, True):
                code = (
                    (
                        "onconnect = e => { const p=e.ports[0]; "
                        f"p.onmessage=async()=>p.postMessage(await ({PROBE})({json.dumps(urls)})); "
                        "p.start(); }"
                    )
                    if shared
                    else f"onmessage=async()=>postMessage(await ({PROBE})({json.dumps(urls)}));"
                )
                result = await page.evaluate(
                    """({code, shared}) => new Promise(resolve => {
                        const url=URL.createObjectURL(new Blob([code], {type:'text/javascript'}));
                        const worker=shared ? new SharedWorker(url) : new Worker(url);
                        const port=shared ? worker.port : worker;
                        if(shared) port.start();
                        const timer=setTimeout(()=>resolve('timeout'), 8000);
                        port.onmessage=e=>{
                            clearTimeout(timer); resolve(e.data);
                            if(shared) port.close(); else worker.terminate();
                            URL.revokeObjectURL(url);
                        };
                        port.postMessage('start');
                    })""",
                    {"code": code, "shared": shared},
                )
                assert result == expected
            assert state.proxy.websocket_blocked_count >= 18
            assert handshakes == []
            # A failed "other proxies" endpoint must not fall back to HTTP/HTTPS or DIRECT.
            state.proxy.websocket_server.close()
            await state.proxy.websocket_server.wait_closed()
            for _ in range(2):
                assert await page.evaluate(PROBE, urls) == expected
            assert (await page.goto(http_url)).status == 200
            assert (await page.goto(https_url)).status == 200
            assert handshakes == []
