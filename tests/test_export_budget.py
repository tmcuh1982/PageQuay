import os

import pytest
from playwright.async_api import async_playwright

from pagequay.frame_context import register_frame_selector
from pagequay.page_reader import isolated_read
from pagequay.structured import SCRIPT, extract_structured

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(os.environ.get("PQ_BROWSER_TESTS") != "1", reason="Use --browser"),
]


@pytest.mark.parametrize(
    "case", ["identity", "large_dom", "hidden_frames", "visible_limit", "inventory_limit"]
)
async def test_export_identity_and_visible_frame_budgets(case):
    async with async_playwright() as p:
        await register_frame_selector(p)
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        if case == "identity":
            await page.set_content(
                "<title>AgXeed fixture</title><main><p>" + ("description " * 3000) + "</p></main>"
            )
            d = await isolated_read(
                page,
                "function(options) { return JSON.stringify({value:(" + SCRIPT + ")(options)}); }",
                {"include_dom": False, "text_budget": 100},
                max_bytes=2000000,
            )
            assert d["url"] == "about:blank" and d["title"] == "AgXeed fixture"
            assert d["stats"]["characters"] <= 100
            assert "text_budget" in d["truncation_reasons"]
        elif case == "large_dom":
            await page.set_content(
                "<title>Large fixture</title><main>"
                + ("<span>Label</span>" * 2500)
                + "<p>Final descriptive evidence retained.</p></main>"
            )
            d = await extract_structured(page)
            assert "nodes" not in d["truncation_reasons"]
            assert any(
                "Final descriptive evidence retained." in b.get("text", "") for b in d["blocks"]
            )
        else:
            hidden = '<iframe style="display:none" srcdoc="hidden"></iframe>' * (
                33 if case == "inventory_limit" else 6
            )
            visible = '<iframe srcdoc="Visible child"></iframe>' * (
                1 if case == "hidden_frames" else 6
            )
            await page.set_content(
                "<title>Frame fixture</title><main><p>Public description.</p></main>"
                + hidden
                + visible
            )
            d = await extract_structured(page)
            if case == "hidden_frames":
                assert not d["frame_limit_reached"]
                assert any(f["status"] == "extracted" for f in d["frames"])
                assert sum(f.get("reason") == "hidden_frame" for f in d["frames"]) == 6
            elif case == "inventory_limit":
                assert d["frame_limit_reached"] and d["partial"]
                assert len(d["frames"]) == 31
            else:
                assert d["frame_limit_reached"] and d["partial"]
                assert sum(f["status"] == "extracted" for f in d["frames"]) == 3
        await browser.close()
