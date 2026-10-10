import asyncio
import os
import socket
from pathlib import Path

import pytest
import uvicorn
from playwright.async_api import async_playwright

from pagequay.auth import PASSWORDS
from pagequay.main import create_app
from pagequay.settings import Settings
from pagequay.storage import uid

OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "testing"

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(
        os.environ.get("PQ_BROWSER_TESTS") != "1", reason="Use --browser for UI integration"
    ),
]


async def test_admin_browser_forms_and_responsive_layout(tmp_path):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    app = create_app(
        Settings(data_dir=tmp_path, allowed_hosts=["127.0.0.1"], allowed_origins=[base])
    )
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            access_log=False,
            log_level="error",
            proxy_headers=False,
        )
    )
    task = asyncio.create_task(server.serve(sockets=[sock]))
    while not server.started:
        if task.done():
            await task
        await asyncio.sleep(0.05)
    rt = app.state.rt
    rt.db.execute(
        "INSERT INTO admins VALUES (?,?,?)",
        (uid(), "admin", PASSWORDS.hash("TestPassword-42-Only!")),
    )
    errors = []
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True, chromium_sandbox=True)
            page = await browser.new_page(viewport={"width": 1440, "height": 1050})
            page.on("pageerror", lambda error: errors.append(str(error)))
            await page.goto(base + "/admin")
            await page.get_by_label("Identifiant", exact=True).fill("admin")
            await page.get_by_label("Mot de passe").fill("TestPassword-42-Only!")
            nonce = await page.locator('input[name="csrf"]').input_value()
            cookies = await page.context.cookies()
            assert next(c["value"] for c in cookies if c["name"] == "pq_login_csrf") == nonce
            async with page.expect_response(
                lambda response: (
                    response.url.endswith("/admin/login") and response.request.method == "POST"
                )
            ) as result:
                await page.get_by_role("button", name="Se connecter").click()
            login_response = await result.value
            assert login_response.status == 303, (
                await login_response.request.header_value("origin"),
                await login_response.text(),
            )
            await page.wait_for_url(base + "/admin")
            await page.goto(base + "/admin/projects")
            for name, slug in [("UniversRobot", "universrobot"), ("Projet B", "projet-b")]:
                await page.locator('form[data-api="/admin/projects"] input[name="name"]').fill(name)
                await page.get_by_label("Identifiant permanent").fill(slug)
                await page.get_by_role("button", name="Créer le projet", exact=True).click()
                await page.wait_for_load_state("load")
                await page.locator(".section-heading h2").filter(has_text=name).wait_for()
            await page.goto(base + "/admin/keys")
            await page.get_by_label("Nom de la clé").fill("Client test UI")
            await page.get_by_role("button", name="Générer la clé").click()
            await page.locator("#secret-panel:not(.hidden)").wait_for()
            secret = await page.locator("#secret-value").inner_text()
            assert secret.startswith("pq_")
            await page.get_by_role("button", name="J’ai conservé la clé").click()
            await page.wait_for_load_state("load")
            await page.locator("table").wait_for()
            assert secret not in await page.content()
            await rt.browser.start(rt.db.project("universrobot"))
            await rt.browser.start(rt.db.project("projet-b"))
            await page.goto(base + "/admin")
            assert await page.locator(".project-row .pill.green").count() == 2
            output = OUTPUT
            output.mkdir(exist_ok=True)
            await page.screenshot(path=str(output / "admin-desktop.png"), full_page=True)
            for view in ("projects", "keys", "sessions", "search", "settings", "audit"):
                response = await page.goto(base + "/admin/" + view)
                assert response.status == 200
                assert await page.locator("h1").count() == 1
            await page.set_viewport_size({"width": 390, "height": 844})
            await page.goto(base + "/admin")
            assert await page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            await page.screenshot(path=str(output / "admin-mobile.png"), full_page=True)
            assert not errors, errors
            await browser.close()
    finally:
        server.should_exit = True
        await task
        sock.close()
