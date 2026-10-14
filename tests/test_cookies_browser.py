import asyncio
import os

import httpx
import pytest
from playwright.async_api import async_playwright
from test_browser import poll, site

from pagequay.cookies import validate_cookies
from pagequay.main import create_app
from pagequay.network import NetworkPolicy
from pagequay.settings import Policy, Settings

test_site = site
pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(os.environ.get("PQ_BROWSER_TESTS") != "1", reason="Use --browser"),
]

BANNER = """<div role="dialog" id="cookie-banner"><p>Cookies : votre choix</p>
<div class="cookie-options"><button onclick="document.body.dataset.choice='reject';
document.querySelector('#cookie-banner').remove()">Refuser</button>
<button onclick="document.body.dataset.choice='accept';
document.querySelector('#cookie-banner').remove()">Tout accepter</button></div></div>"""


@pytest.fixture
async def page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        yield await browser.new_page()
        await browser.close()


async def test_choices_nested_containers_no_banner_and_missing_choice(page):
    for choice in ("reject", "accept"):
        await page.set_content(BANNER)
        assert await validate_cookies(page, choice=choice, timeout_ms=500) == {
            "choice": choice,
            "status": "clicked",
        }
        assert await page.locator("body").get_attribute("data-choice") == choice
    await page.set_content("<article>Cookies information</article><button>Refuser</button>")
    assert (await validate_cookies(page, timeout_ms=100))["status"] == "not_found"
    await page.set_content('<div role="dialog">Cookies<button>Tout accepter</button></div>')
    assert (await validate_cookies(page, timeout_ms=150))["status"] == "choice_unavailable"
    assert await page.get_by_role("button").count() == 1


async def test_cross_origin_banner_and_custom_container(page):
    await page.route(
        "https://consent.example/**",
        lambda route: route.fulfill(body=BANNER, content_type="text/html"),
    )
    await page.set_content('<iframe src="https://consent.example/banner"></iframe>')
    assert (await validate_cookies(page, timeout_ms=1500))["status"] == "clicked"
    await page.set_content(
        BANNER.replace('role="dialog" id="cookie-banner"', 'id="custom"')
        .replace(
            "document.querySelector('#cookie-banner').remove()",
            "document.querySelector('#custom').remove()",
        )
        .replace('class="cookie-options"', 'class="options"')
    )
    assert (await validate_cookies(page, timeout_ms=100))["status"] == "not_found"
    assert (await validate_cookies(page, selector="#custom", timeout_ms=1000))[
        "status"
    ] == "clicked"


async def test_delayed_shadow_and_frame_banners(page):
    await page.set_content('<div id="host"></div>')
    await page.evaluate(
        """html => setTimeout(() => {
      document.querySelector('#host').attachShadow({mode:'open'}).innerHTML = html;
    }, 150)""",
        BANNER.replace(
            "document.querySelector('#cookie-banner').remove()",
            "this.closest('#cookie-banner').remove()",
        ),
    )
    assert (await validate_cookies(page, timeout_ms=1500))["status"] == "clicked"
    await page.set_content("<iframe></iframe>")
    frame = page.frames[1]
    await frame.set_content(BANNER)
    assert (await validate_cookies(page, timeout_ms=1000))["status"] == "clicked"
    assert await frame.locator("body").get_attribute("data-choice") == "reject"
    await frame.set_content(BANNER)
    await page.locator("iframe").evaluate("el => el.style.display = 'none'")
    assert (await validate_cookies(page, timeout_ms=100))["status"] == "not_found"


async def test_ambiguous_disabled_and_scan_limit(page):
    await page.set_content(BANNER + BANNER.replace("cookie-banner", "cookie-banner-two"))
    assert (await validate_cookies(page, timeout_ms=500))["status"] == "ambiguous"
    assert await page.locator("body").get_attribute("data-choice") is None
    await page.set_content(BANNER.replace("<button onclick", "<button disabled onclick"))
    assert (await validate_cookies(page, timeout_ms=150))["status"] == "timeout"
    await page.set_content(BANNER + "<iframe></iframe>" * 8)
    assert (await validate_cookies(page, timeout_ms=500))["status"] == "scan_limit"


async def test_api_action_persistent_visits_and_websocket(tmp_path, test_site):
    port, _ = test_site

    def factory(policy):
        return NetworkPolicy(policy, test_allowed_hosts={"localhost"}, test_ports={port})

    app = create_app(
        Settings(data_dir=tmp_path, policy=Policy(headless=True), allowed_hosts=["testserver"]),
        network_factory=factory,
    )
    async with app.router.lifespan_context(app):
        rt = app.state.rt
        project = rt.db.create_project("project-x", "Project X")
        _, token = rt.auth.create_key(project, "test", ["browser:interact", "browser:read"])
        headers = {"Authorization": "Bearer " + token}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            base = "/v1/projects/project-x"
            response = await client.post(
                base + "/tabs", json={"url": f"http://localhost:{port}/"}, headers=headers
            )
            assert response.status_code == 202, response.text
            row = await poll(client, "project-x", response.json()["job_id"], headers)
            tab = rt.browser.tab(project, row["tab_id"])
            await tab.page.set_content(BANNER)
            response = await client.post(
                base + f"/tabs/{tab.id}/actions",
                headers=headers,
                json={"actions": [{"type": "validate_cookies"}]},
            )
            row = await poll(client, "project-x", response.json()["job_id"], headers)
            assert row["result"]["cookie_consent"][0]["status"] == "clicked"
            response = await client.put(
                base + "/cookie-policy",
                headers=headers,
                json={"choice": "reject", "timeout_ms": 500},
            )
            assert response.status_code == 200
            await tab.page.route(
                "**/consent", lambda route: route.fulfill(body=BANNER, content_type="text/html")
            )
            for _ in range(2):
                response = await client.post(
                    base + f"/tabs/{tab.id}/navigate",
                    headers=headers,
                    json={"url": f"http://localhost:{port}/consent"},
                )
                row = await poll(client, "project-x", response.json()["job_id"], headers)
                assert row["result"]["cookie_consent"]["status"] == "clicked"
                assert await tab.page.locator("body").get_attribute("data-choice") == "reject"
            await client.put(base + "/cookie-policy", headers=headers, json={"choice": None})
            await tab.page.set_content(BANNER)
            from pagequay.api import ws_command

            result = await ws_command(
                rt,
                project,
                rt.auth.key(token),
                {
                    "type": "actions",
                    "tab_id": tab.id,
                    "actions": [{"type": "validate_cookies", "value": "accept"}],
                },
            )
            row = await poll(client, "project-x", result["job_id"], headers)
            assert row["result"]["cookie_consent"][0]["choice"] == "accept"
            await asyncio.sleep(0)
