"""Reproduire le cadre consentement dimensionné que is_visible considère visible."""

import os

import pytest
from playwright.async_api import async_playwright

from pagequay.frame_context import register_frame_selector
from pagequay.structured import extract_structured

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(os.environ.get("PQ_BROWSER_TESTS") != "1", reason="Use --browser"),
]


async def test_sized_aria_hidden_frames_do_not_consume_content_slots():
    async with async_playwright() as p:
        await register_frame_selector(p)
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            technical = (
                '<iframe aria-hidden="true" style="width:4px;height:4px" '
                'srcdoc="Technical consent content"></iframe>'
            )
            await page.set_content(
                "<main><p>Manual descriptive content.</p></main>"
                + technical * 6
                + '<iframe srcdoc="Real visible child content"></iframe>'
            )
            assert await page.locator('iframe[aria-hidden="true"]').first.is_visible()
            doc = await extract_structured(page)
            assert len([f for f in doc["frames"] if f["status"] == "omitted"]) == 6
            assert len([f for f in doc["frames"] if f["status"] == "extracted"]) == 1
            assert not doc["partial"]
            assert not doc["frame_limit_reached"]
            assert "Real visible child content" in str(doc["frames"][-1]["document"]["blocks"])
        finally:
            await browser.close()
