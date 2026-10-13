import os

import pytest
from playwright.async_api import async_playwright

from pagequay.diagnostics import ReadTrace
from pagequay.frame_context import register_frame_selector
from pagequay.models import ContextSelectionDiagnostic
from pagequay.page_reader import SCRIPT, isolated_read

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(os.environ.get("PQ_BROWSER_TESTS") != "1", reason="Use --browser"),
]


@pytest.mark.parametrize("mode", ["open", "closed"])
@pytest.mark.parametrize("nested", [False, True])
async def test_isolated_cross_site_shadow_frame(mode, nested):
    async with async_playwright() as p:
        await register_frame_selector(p)
        browser = await p.chromium.launch(headless=True, args=["--site-per-process"])
        page = await browser.new_page()

        async def site(route):
            if "parent.test" in route.request.url:
                html = (
                    '<div id="host"></div><script>'
                    f'document.querySelector("#host").attachShadow({{mode:"{mode}"}}).innerHTML='
                    '\'<iframe src="http://child.test/" '
                    'style="width:400px;height:200px"></iframe>\';</script>'
                )
            elif route.request.url == "http://child.test/":
                html = "<title>Child fixture</title><p>Child evidence</p>"
                if nested:
                    html += '<iframe src="http://child.test/grand"></iframe>'
            else:
                html = "<title>Wrong nested child</title>"
            await route.fulfill(content_type="text/html", body=html)

        await page.route("**/*", site)
        await page.goto("http://parent.test/", wait_until="load")
        child = next(f for f in page.frames if f.url == "http://child.test/")
        assert await page.evaluate("window.length") == 0
        trace = ReadTrace(child)
        result = await isolated_read(
            page,
            SCRIPT,
            {"kind": "title", "max_bytes": 16384},
            frame=child,
            max_bytes=200000,
            trace=trace,
        )
        assert result["title"] == "Child fixture"
        assert (
            ContextSelectionDiagnostic.model_validate(trace.selection).path_source
            == "frame_target_root"
        )
        await browser.close()
