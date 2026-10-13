import os
from types import SimpleNamespace

import pytest
from playwright.async_api import async_playwright

from pagequay.browser import challenge_state

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(os.environ.get("PQ_BROWSER_TESTS") != "1", reason="Use --browser"),
]


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        (
            '<h1>AgXeed</h1><p>Autonomous agricultural robots.</p><iframe style="display:none" src="https://captcha.invalid/recaptcha"></iframe>',
            None,
        ),
        (
            '<h1>AgXeed</h1><p>Autonomous agricultural robots.</p><iframe width="300" height="78" src="https://captcha.invalid/recaptcha"></iframe>',
            None,
        ),
        (
            '<iframe style="position:fixed;inset:0;width:100vw;height:100vh" src="https://captcha.invalid/recaptcha"></iframe>',
            "human",
        ),
        ('<div data-pq-challenge="true">Challenge fixture</div>', "human"),
        (
            '<h1>Verify you are human</h1><iframe width="300" height="78" src="https://captcha.invalid/recaptcha"></iframe>',
            "human",
        ),
        ("<title>Just a moment</title><p>Checking your browser</p>", "automatic"),
    ],
)
async def test_widget_is_distinct_from_blocking_challenge(html, expected):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 900})
        await page.route("**/*", lambda route: route.abort())
        await page.set_content(html)
        assert await challenge_state(page, evidence=SimpleNamespace(cf_challenge=False)) == expected
        await browser.close()
