import os

import pytest
from playwright.async_api import async_playwright

from pagequay.structured import extract_structured

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(os.environ.get("PQ_BROWSER_TESTS") != "1", reason="Use --browser"),
]


@pytest.mark.parametrize("hidden", [True, False])
async def test_hidden_blob_is_omitted_but_visible_blob_stays_unavailable(hidden):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content("<main><p>Main public description.</p></main>")
        await page.evaluate(
            """hidden => new Promise(resolve => {
            const frame = document.createElement('iframe');
            frame.style.cssText = hidden ? 'display:none' : 'width:400px;height:200px';
            frame.onload = resolve;
            frame.src = URL.createObjectURL(new Blob(['<p>Blob fixture</p>'], {type:'text/html'}));
            document.body.append(frame);
        })""",
            hidden,
        )
        result = await extract_structured(page)
        child = result["frames"][0]
        assert child["status"] == ("omitted" if hidden else "unavailable")
        assert child["reason"] == ("hidden_frame" if hidden else "unsupported_frame_scheme")
        assert result["partial"] is (not hidden)
        assert "document" not in child
        await browser.close()
