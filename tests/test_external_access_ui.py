import asyncio
import os
import socket
from pathlib import Path

import pytest
import uvicorn
from playwright.async_api import async_playwright
from test_external_access import HOST, ServeCLI

from pagequay.auth import PASSWORDS
from pagequay.errors import PQError
from pagequay.external_access import ExternalAccess
from pagequay.main import create_app
from pagequay.settings import Settings
from pagequay.storage import uid


@pytest.mark.browser
@pytest.mark.skipif(os.environ.get("PQ_BROWSER_TESTS") != "1", reason="Use --browser")
async def test_external_access_form_in_browser(tmp_path, monkeypatch):
    cli = ServeCLI()
    unavailable = False

    async def run(self, *args):
        if unavailable:
            raise PQError("UNAVAILABLE", "Tailscale indisponible.", 503)
        return await cli.run(*args)

    monkeypatch.setattr(ExternalAccess, "_run", run)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    base = f"http://127.0.0.1:{sock.getsockname()[1]}"
    app = create_app(
        Settings(data_dir=tmp_path, allowed_hosts=["127.0.0.1", HOST], allowed_origins=[base])
    )
    server = uvicorn.Server(
        uvicorn.Config(app, access_log=False, log_level="error", proxy_headers=False)
    )
    task = asyncio.create_task(server.serve(sockets=[sock]))
    while not server.started:
        if task.done():
            await task
        await asyncio.sleep(0.05)
    app.state.rt.db.execute(
        "INSERT INTO admins VALUES (?,?,?)",
        (uid(), "admin", PASSWORDS.hash("TestPassword-42-Only!")),
    )
    errors = []
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True, chromium_sandbox=True)
            page = await browser.new_page(viewport={"width": 1440, "height": 1050})
            page.on("pageerror", lambda error: errors.append(str(error)))
            await page.goto(base + "/admin/login")
            await page.get_by_label("Identifiant", exact=True).fill("admin")
            await page.get_by_label("Mot de passe", exact=True).fill("TestPassword-42-Only!")
            await page.get_by_role("button", name="Se connecter").click()
            await page.wait_for_url(base + "/admin")
            unavailable = True
            await page.goto(base + "/admin/settings")
            assert await page.get_by_role("button", name="Appliquer le port HTTPS").is_disabled()
            assert await page.get_by_role("button", name="Enregistrer le port local").is_enabled()
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                local_port = probe.getsockname()[1]
            await page.get_by_label("Port API local").fill(str(local_port))
            async with page.expect_response(base + "/admin/settings/local-access") as local:
                await page.get_by_role("button", name="Enregistrer le port local").click()
            assert (await local.value).status == 200
            assert (await local.value).request.post_data_json == {
                "api_port": local_port,
                "configured_port": 8766,
            }
            await page.get_by_text(f"Port {local_port} enregistré.", exact=False).wait_for()
            assert app.state.rt.settings.api_port == 8766
            unavailable = False
            await page.reload()
            assert await page.get_by_label("Port HTTPS externe").input_value() == "443"
            await page.get_by_label("Port HTTPS externe").fill("8443")
            async with page.expect_response(base + "/admin/settings/external-access") as saved:
                await page.get_by_role("button", name="Appliquer le port HTTPS").click()
            response = await saved.value
            assert response.status == 200
            assert response.request.post_data_json == {"https_port": 8443, "current_port": 443}
            await page.wait_for_function(
                'document.querySelector("input[name=https_port]")?.value === "8443" && '
                'document.querySelector("input[name=current_port]")?.value === "8443"'
            )
            assert (
                await page.get_by_role("link", name=f"https://{HOST}:8443", exact=True).count() == 1
            )
            output = Path("/tmp/pagequay-external-access")
            await asyncio.to_thread(output.mkdir, exist_ok=True)
            await page.screenshot(path=str(output / "desktop.png"), full_page=True)
            await page.set_viewport_size({"width": 390, "height": 844})
            assert await page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            await page.screenshot(path=str(output / "mobile.png"), full_page=True)
            # Initial activation sends null for an absent old port, not numeric zero.
            cli.config = {"TCP": {}, "Web": {}}
            await page.reload()
            async with page.expect_response(base + "/admin/settings/external-access") as created:
                await page.get_by_role("button", name="Appliquer le port HTTPS").click()
            assert (await created.value).request.post_data_json["current_port"] is None
            assert (await created.value).status == 200
            assert not errors
            await browser.close()
    finally:
        server.should_exit = True
        await task
        sock.close()
