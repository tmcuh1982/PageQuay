import asyncio
import os
import socket
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import uvicorn
from playwright.async_api import async_playwright

from pagequay.admin import LOGIN_CSRF_COOKIE
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
            assert next(c["value"] for c in cookies if c["name"] == LOGIN_CSRF_COOKIE) == nonce
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
            expiration_toggle = page.get_by_label("Définir une date d’expiration", exact=True)
            expiration_date = page.get_by_label("Date et heure d’expiration", exact=True)
            future = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
            assert await expiration_date.is_disabled()
            assert await expiration_date.input_value() == ""
            await expiration_toggle.check()
            await expiration_date.fill(future)
            await expiration_toggle.uncheck()
            assert await expiration_date.is_disabled()
            assert await expiration_date.input_value() == ""
            assert (
                "60 requêtes par minute et par clé"
                in await page.locator("[data-key-project-rate-help]").inner_text()
            )
            await page.get_by_label("Nom de la clé").fill("Client test UI")
            async with page.expect_response(
                lambda response: (
                    response.url.endswith("/keys") and response.request.method == "POST"
                )
            ) as created:
                await page.get_by_role("button", name="Générer la clé").click()
            assert (await created.value).request.post_data_json["expires_at"] is None
            assert (
                rt.db.one("SELECT expires_at FROM api_keys WHERE name='Client test UI'")[
                    "expires_at"
                ]
                is None
            )
            await page.locator("#secret-panel:not(.hidden)").wait_for()
            secret = await page.locator("#secret-value").inner_text()
            assert secret.startswith("pq_")
            await page.get_by_role("button", name="J’ai conservé la clé").click()
            await page.wait_for_load_state("load")
            await page.locator("table").wait_for()
            assert secret not in await page.content()
            assert "Sans expiration" in await page.locator("table").inner_text()
            await page.get_by_label("Nom de la clé").fill("Client avec expiration")
            await expiration_toggle.check()
            await expiration_date.fill(future)
            await page.get_by_role("button", name="Générer la clé").click()
            await page.locator("#secret-panel:not(.hidden)").wait_for()
            assert (
                rt.db.one("SELECT expires_at FROM api_keys WHERE name='Client avec expiration'")[
                    "expires_at"
                ]
                is not None
            )
            await page.get_by_role("button", name="J’ai conservé la clé").click()
            await page.locator("table").wait_for()
            row = page.get_by_role("row").filter(has_text="Client test UI")
            await row.get_by_role("link", name="Modifier la sécurité").click()
            assert await page.get_by_label("Nom de la clé").input_value() == "Client test UI"
            assert await page.get_by_label("Projet", exact=True).is_disabled()
            assert await expiration_date.is_disabled()
            await page.get_by_label("browser:read", exact=True).check()
            await page.get_by_label("search:read", exact=True).uncheck()
            await page.get_by_label("Requêtes / minute", exact=True).fill("17")
            await expiration_toggle.check()
            await expiration_date.fill(future)
            await page.get_by_role("button", name="Enregistrer les modifications").click()
            await page.wait_for_url(base + "/admin/keys")
            updated_key = rt.auth.key(secret)
            assert updated_key["rate_limit"] == 17
            assert updated_key["scopes"] == ["browser:read", "content:read"]
            assert updated_key["expires_at"] is not None
            await row.get_by_role("link", name="Modifier la sécurité").click()
            assert await expiration_toggle.is_checked()
            assert (await expiration_date.input_value()).startswith(future)
            await page.screenshot(path=str(OUTPUT / "key-edit-desktop.png"), full_page=True)
            await page.set_viewport_size({"width": 390, "height": 844})
            assert await page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            await page.screenshot(path=str(OUTPUT / "key-edit-mobile.png"), full_page=True)
            await page.set_viewport_size({"width": 1440, "height": 1050})
            await expiration_toggle.uncheck()
            await page.get_by_role("button", name="Enregistrer les modifications").click()
            await page.wait_for_url(base + "/admin/keys")
            assert rt.auth.key(secret)["expires_at"] is None
            await row.get_by_role("link", name="Modifier la sécurité").click()
            await page.get_by_label("Requêtes / minute", exact=True).fill("3")
            await page.get_by_role("link", name="Annuler", exact=True).click()
            await page.wait_for_url(base + "/admin/keys")
            assert rt.auth.key(secret)["rate_limit"] == 17
            await page.screenshot(path=str(OUTPUT / "keys-desktop.png"), full_page=True)
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
            await page.goto(base + "/admin/settings")
            toggle = page.get_by_label("Démarrer les fenêtres minimisées", exact=True)
            await toggle.check()
            config = page.locator('form[data-api="/admin/settings"] textarea')
            assert '"browser_start_minimized": true' in await config.input_value()
            async with page.expect_response(base + "/admin/settings") as saved:
                await page.locator('form[data-api="/admin/settings"] button').click()
            assert (await saved.value).status == 200
            await page.wait_for_load_state("load")
            assert rt.db.policy().browser_start_minimized
            await page.goto(base + "/admin/sessions")
            state = rt.browser.states[rt.db.project("universrobot")["id"]]
            for operation, expected in (("minimize", "minimized"), ("restore", "normal")):
                url = f"/admin/projects/universrobot/browser/{operation}"
                async with page.expect_response(base + url) as changed:
                    await page.locator(f'button[data-post="{url}"]').click()
                assert (await changed.value).status == 200
                await page.wait_for_load_state("load")
                window = await rt.browser._window(state, state.context.pages[0])
                assert window["bounds"]["windowState"] == expected
            await page.screenshot(
                path=str(output / "sessions-minimize-desktop.png"), full_page=True
            )
            await page.set_viewport_size({"width": 390, "height": 844})
            await page.goto(base + "/admin/keys")
            assert await page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            await page.screenshot(path=str(output / "keys-mobile.png"), full_page=True)
            await page.goto(base + "/admin")
            assert await page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            await page.screenshot(path=str(output / "admin-mobile.png"), full_page=True)
            assert not errors, errors
            await browser.close()
    finally:
        server.should_exit = True
        await task
        sock.close()
