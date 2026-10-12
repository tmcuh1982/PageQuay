import asyncio
import os
import socket
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

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
            page = await browser.new_page(
                viewport={"width": 1440, "height": 1050}, timezone_id="Europe/Warsaw"
            )
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
            await page.locator("[data-api-chart] rect").first.wait_for(state="attached")
            assert await page.locator("[data-api-empty]").is_visible()
            for endpoint in ["GET /v1/projects/{slug}/tabs"] * 3 + [
                "POST /v1/projects/{slug}/search"
            ]:
                rt.db.audit("api.request", actor="api", details={"endpoint": endpoint})
            await page.reload()
            await page.locator("[data-api-total]").filter(has_text="4 appels").wait_for()
            assert await page.locator("[data-api-chart] rect").count() == 24
            assert await page.locator("[data-api-group]").input_value() == "project"
            assert await page.locator("[data-api-mini-chart]").count() == 1
            await page.locator("[data-api-group]").select_option("endpoint")
            assert await page.locator("[data-api-mini-chart]").count() == 2
            await page.locator("[data-api-type]").select_option("Recherche")
            assert await page.locator("[data-api-total]").inner_text() == "1 appel"
            assert await page.locator("[data-api-mini-chart]").count() == 1
            await page.locator("[data-api-type]").select_option("")
            await page.locator("[data-api-group]").select_option("key")
            assert await page.locator("[data-api-mini-chart]").count() == 1
            assert await page.locator("[data-api-key-note]").is_visible()
            assert "Clé non renseignée" in await page.locator(".api-mini h3").inner_text()
            await page.locator("[data-api-group]").select_option("endpoint")
            assert "Europe/Warsaw" in await page.locator("[data-api-timezone]").inner_text()
            current_hour = datetime.now(ZoneInfo("Europe/Warsaw")).strftime("%H:00")
            assert current_hour in await page.locator("[data-api-chart] rect").last.get_attribute(
                "aria-label"
            )
            await page.locator("[data-api-endpoint]").select_option(
                "POST /v1/projects/{slug}/search"
            )
            assert await page.locator("[data-api-total]").inner_text() == "1 appel"
            assert not await page.locator("[data-api-empty]").is_visible()
            await page.screenshot(path=str(OUTPUT / "api-usage-desktop.png"), full_page=True)
            await page.set_viewport_size({"width": 390, "height": 844})
            assert await page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            await page.screenshot(path=str(OUTPUT / "api-usage-mobile.png"), full_page=True)
            await page.set_viewport_size({"width": 1440, "height": 1050})
            await page.goto(base + "/admin/projects")
            for name, slug in [("UniversRobot", "universrobot"), ("Projet B", "projet-b")]:
                await page.locator('form[data-api="/admin/projects"] input[name="name"]').fill(name)
                await page.get_by_label("Identifiant permanent").fill(slug)
                await page.get_by_role("button", name="Créer le projet", exact=True).click()
                await page.wait_for_load_state("load")
                await page.locator(".section-heading h2").filter(has_text=name).wait_for()
            project = rt.db.project("universrobot")
            profile = rt.db.root / "profiles" / project["id"]
            for filename in ["Preview/Network/Cookies", "Preview/Cache/Cache_Data/image"]:
                fixture = profile / filename
                fixture.parent.mkdir(parents=True, exist_ok=True)
                fixture.write_bytes(b"profile disk fixture" * 800)
            await page.goto(base + "/admin")
            assert await page.locator("[data-profile-disk]").count() == 2
            disk = page.locator(f'[data-profile-disk="{project["id"]}"]')
            assert (
                "0 o"
                != await disk.locator(".profile-disk-heading div:last-child strong").inner_text()
            )
            await page.screenshot(
                path=str(OUTPUT / "api-profile-overview-desktop.png"), full_page=True
            )
            await page.set_viewport_size({"width": 390, "height": 844})
            assert await page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            await page.screenshot(
                path=str(OUTPUT / "api-profile-overview-mobile.png"), full_page=True
            )
            await page.set_viewport_size({"width": 1440, "height": 1050})
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
            key_project = rt.db.one(
                "SELECT slug,name FROM projects WHERE id=?", (rt.auth.key(secret)["project_id"],)
            )
            api_response = await page.request.get(
                base + f"/v1/projects/{key_project['slug']}/key-info",
                headers={"Authorization": "Bearer " + secret},
            )
            assert api_response.status == 200
            await page.goto(base + "/admin")
            await page.locator("[data-api-group]").select_option("project")
            assert key_project["name"] in await page.locator("[data-api-graphs]").inner_text()
            await page.locator("[data-api-type]").select_option("Informations de clé")
            assert await page.locator("[data-api-total]").inner_text() == "1 appel"
            assert await page.locator("[data-api-mini-chart]").count() == 1
            await page.locator("[data-api-group]").select_option("key")
            assert "Client test UI" in await page.locator(".api-mini h3").inner_text()
            assert secret not in await page.content()
            await page.locator(".api-usage").screenshot(path=str(OUTPUT / "api-key-chart.png"))
            await page.goto(base + "/admin/keys")
            await page.screenshot(path=str(OUTPUT / "keys-desktop.png"), full_page=True)
            await rt.browser.start(rt.db.project("universrobot"))
            await rt.browser.start(rt.db.project("projet-b"))
            await page.goto(base + "/admin")
            assert await page.locator(".project-row .pill.green").count() == 2
            output = OUTPUT
            output.mkdir(exist_ok=True)
            await page.screenshot(path=str(output / "admin-desktop.png"), full_page=True)
            rt.db.audit(
                "function.submit_search_form",
                rt.db.project("universrobot")["id"],
                details={
                    "function": "submit_search_form",
                    "label": "next page",
                    "url": "https://example.org/page1",
                    "result_url": "https://example.org/page2",
                    "job_id": "audit-ui",
                    "duration_ms": 2345,
                },
            )
            rt.db.audit(
                "network.response",
                rt.db.project("universrobot")["id"],
                details={
                    "url": "https://example.org/page2",
                    "downloaded_bytes": 3072,
                    "duration_ms": 125,
                    "http_status": 200,
                    "job_id": "audit-ui",
                    "resource_type": "document",
                },
            )
            rt.db.audit(
                "job.timezone_fixture",
                rt.db.project("universrobot")["id"],
                details={"job_id": "timezone-ui"},
            )
            await rt.db.telemetry.flush_async()
            rt.db.execute(
                "UPDATE audit SET at=? WHERE action='job.timezone_fixture'",
                (datetime(2026, 10, 10, 20, 46, tzinfo=UTC).timestamp(),),
            )
            for view in ("projects", "keys", "sessions", "search", "settings", "audit"):
                response = await page.goto(base + "/admin/" + view)
                assert response.status == 200
                assert await page.locator("h1").count() == 1
                if view == "audit":
                    assert await page.locator(".audit-table .pill").inner_text() == "next page"
                    assert "3.00" in await page.locator(".audit-table").inner_text()
                    assert await page.get_by_role("columnheader", name="Durée").count() == 1
                    durations = await page.locator(".audit-duration").all_text_contents()
                    assert "125 ms" in durations and "2.35 s" in durations and "—" in durations
                    assert await page.get_by_role("columnheader", name="Date locale").count() == 1
                    assert (
                        "2026-10-10 22:46" in await page.locator(".audit-date").all_text_contents()
                    )
                    job_option = page.locator('select[name="job"] option[value="timezone-ui"]')
                    assert (await job_option.inner_text()).endswith("2026-10-10 22:46")
                    assert "UTC" not in await job_option.inner_text()
                    await page.get_by_role("combobox", name="Job", exact=True).select_option(
                        "audit-ui"
                    )
                    await page.get_by_label("Type", exact=True).select_option("functions")
                    async with page.expect_navigation():
                        await page.get_by_role("button", name="Filtrer", exact=True).click()
                    assert await page.locator(".audit-table tbody tr").count() == 1
                    assert await page.get_by_label("Type", exact=True).input_value() == "functions"
                    heights = await page.locator(
                        ".audit-filters input, .audit-filters select, .audit-filters button"
                    ).evaluate_all("els => els.map(el => el.getBoundingClientRect().height)")
                    assert max(heights) - min(heights) <= 1
                    assert (
                        await page.get_by_label("Depuis", exact=True).get_attribute("type")
                        == "datetime-local"
                    )
                    for name, seconds in (
                        ("last 10 min", 600),
                        ("last hour", 3600),
                        ("Today", None),
                    ):
                        async with page.expect_navigation():
                            await page.get_by_role("button", name=name, exact=True).click()
                        params = parse_qs(urlsplit(page.url).query)
                        assert params["job"] == ["audit-ui"]
                        assert params["category"] == ["functions"]
                        since = datetime.fromisoformat(params["since"][0])
                        until = datetime.fromisoformat(params["until"][0])
                        if seconds is not None:
                            assert (until - since).total_seconds() == seconds
                        else:
                            midnight = since.astimezone(ZoneInfo("Europe/Warsaw"))
                            assert (midnight.hour, midnight.minute, midnight.second) == (0, 0, 0)
                            assert (
                                midnight.date()
                                == until.astimezone(ZoneInfo("Europe/Warsaw")).date()
                            )
                        assert await page.get_by_label("Depuis", exact=True).input_value()
                    await page.get_by_label("Depuis", exact=True).fill("2026-10-10T15:20:30")
                    await page.get_by_label("Jusqu’au", exact=True).fill("2026-10-10T16:25:45")
                    async with page.expect_navigation():
                        await page.get_by_role("button", name="Filtrer", exact=True).click()
                    params = parse_qs(urlsplit(page.url).query)
                    assert params["since"] == ["2026-10-10T13:20:30.000Z"]
                    assert params["until"] == ["2026-10-10T14:25:45.000Z"]
                    assert (
                        await page.get_by_label("Depuis", exact=True).input_value()
                        == "2026-10-10T15:20:30"
                    )
                    async with page.expect_navigation():
                        await page.get_by_role("button", name="last 10 min", exact=True).click()
                    scroll = page.locator("[data-audit-scroll]")
                    slider = page.get_by_role("slider", name="Défilement horizontal des colonnes")
                    assert await slider.is_enabled()
                    await page.get_by_role("button", name="Défiler vers la droite").click()
                    assert await scroll.evaluate("el => el.scrollLeft > 0")
                    await slider.focus()
                    await slider.press("End")
                    last = await page.locator(".audit-table th:last-child").bounding_box()
                    bounds = await scroll.bounding_box()
                    assert last["x"] + last["width"] <= bounds["x"] + bounds["width"] + 1
                    assert await page.get_by_role(
                        "button", name="Défiler vers la droite"
                    ).is_disabled()
                    await page.screenshot(path=str(output / "audit-desktop.png"), full_page=True)
                    await slider.press("Home")
                    assert await scroll.evaluate("el => el.scrollLeft == 0")
                if view == "search":
                    await page.locator(
                        'form[data-api-project="search"] [name="project"]'
                    ).select_option("universrobot")
                    search_url = base + "/admin/projects/universrobot/search"
                    submitted = []

                    async def capture_search(route, request, submitted=submitted):
                        submitted.append(route.request.post_data_json)
                        await route.fulfill(json={"job_id": "filter-ui"})

                    await page.route(search_url, capture_search)
                    await page.route(
                        base + "/admin/projects/universrobot/jobs/filter-ui",
                        lambda route: route.fulfill(
                            json={"status": "completed", "result": {"results": []}}
                        ),
                    )
                    country = page.get_by_label("Pays / région")
                    period = page.get_by_label("Période")
                    assert await country.is_disabled() and await period.is_disabled()
                    await page.get_by_label("Moteur").select_option("duckduckgo")
                    assert await country.is_enabled() and await period.is_enabled()
                    await country.select_option("pl-pl")
                    await period.select_option("week")
                    await page.get_by_label("Votre recherche", exact=True).fill("robot agriculture")
                    async with page.expect_response(search_url):
                        await page.get_by_role("button", name="Lancer la recherche").click()
                    assert submitted[-1]["region"] == "pl-pl"
                    assert submitted[-1]["time_range"] == "week"
                    await page.screenshot(
                        path=str(output / "search-filters-desktop.png"), full_page=True
                    )
                    await page.set_viewport_size({"width": 390, "height": 844})
                    assert await page.evaluate(
                        "document.documentElement.scrollWidth <= window.innerWidth"
                    )
                    await page.screenshot(
                        path=str(output / "search-filters-mobile.png"), full_page=True
                    )
                    await page.set_viewport_size({"width": 1440, "height": 1050})
                    await page.get_by_label("Moteur").select_option("google")
                    assert await country.is_disabled() and await period.is_disabled()
                    async with page.expect_response(search_url):
                        await page.get_by_role("button", name="Lancer la recherche").click()
                    assert "region" not in submitted[-1] and "time_range" not in submitted[-1]
                    await page.get_by_label("Moteur").select_option("duckduckgo")
                    await country.select_option("")
                    await period.select_option("any")
                    async with page.expect_response(search_url):
                        await page.get_by_role("button", name="Lancer la recherche").click()
                    assert "region" not in submitted[-1] and submitted[-1]["time_range"] == "any"
                    await page.unroute(search_url, capture_search)
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
            await page.goto(base + "/admin/audit?job=audit-ui")
            assert await page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            slider = page.get_by_role("slider", name="Défilement horizontal des colonnes")
            await slider.focus()
            await slider.press("End")
            last = await page.locator(".audit-table th:last-child").bounding_box()
            bounds = await page.locator("[data-audit-scroll]").bounding_box()
            assert last["x"] + last["width"] <= bounds["x"] + bounds["width"] + 1
            await page.screenshot(path=str(output / "audit-mobile.png"), full_page=True)
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
