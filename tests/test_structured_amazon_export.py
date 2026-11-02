"""Amazon : état technique de frame long, URL longue et DOM dense sans perte."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from playwright.async_api import async_playwright
from test_structured_clearpath_frames import Frame

from pagequay import structured


@pytest.mark.browser
@pytest.mark.parametrize("name_length,partial", [(97226, False), (131073, True)])
async def test_long_frame_name_and_link_remain_exact_under_finite_caps(name_length, partial):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.route("**/*", lambda route: route.abort())
            await page.set_content(
                "<main><p>Public robot product evidence</p><a>Public reference</a>"
                "<iframe></iframe></main>"
            )
            url = "https://example.org/reference?x=" + "a" * 2300
            await page.locator("a").evaluate("(el,url)=>el.href=url", url)
            await page.locator("iframe").evaluate('(el,n)=>el.name="x".repeat(n)', name_length)
            value = await page.evaluate(
                structured.SCRIPT, {"include_dom": True, "text_budget": 1_000_000}
            )
            assert value["truncated"] is partial
            assert value["links"][0]["url"] == url

            def frame(node):
                if node["tag"] == "iframe":
                    return node
                for child in node.get("children", []):
                    result = frame(child)
                    if result:
                        return result

            assert frame(value["dom"]["root"])["attributes"]["name"] == "x" * min(
                name_length, 131072
            )
        finally:
            await browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("count,partial", [(260, False), (401, True)])
async def test_realistic_controls_with_dense_dom_and_overflow(count, partial):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.set_content(
                "<main><p>Robot product information</p>"
                + "<span></span>" * 9000
                + '<button type="button">Option</button>' * count
                + "</main>"
            )
            value = await page.evaluate(
                structured.SCRIPT, {"include_dom": False, "text_budget": 1_000_000}
            )
            assert value["truncated"] is partial
            assert len(value["controls"]) == min(count, 400)
            assert value["stats"]["nodes_visited"] > 8000
        finally:
            await browser.close()


@pytest.mark.parametrize("length,partial", [(97226, False), (131073, True)])
async def test_frame_inventory_names_are_never_silently_clipped(monkeypatch, length, partial):
    main = Frame()
    child = Frame(main)
    child.name = "x" * length
    reader = AsyncMock(return_value={"blocks": [], "truncated": False, "truncation_reasons": []})
    monkeypatch.setattr(structured, "isolated_read", reader)
    value = await structured.extract_structured(
        SimpleNamespace(main_frame=main, frames=[main, child]), max_bytes=4_000_000
    )
    assert value["frames"][0]["name"] == "x" * min(length, 131072)
    assert value["partial"] is partial and value["truncated"] is partial
    if partial:
        assert "frame_name" in value["truncation_reasons"]
