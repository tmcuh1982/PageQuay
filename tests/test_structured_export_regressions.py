"""Long descriptive attributes and verified empty initial frames stay lossless."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from playwright.async_api import async_playwright
from test_structured_clearpath_frames import Frame

from pagequay import structured


@pytest.mark.parametrize("empty", [True, False, None])
async def test_empty_url_frames_are_omitted_only_after_exact_empty_attestation(monkeypatch, empty):
    main = Frame()
    child = Frame(main)
    child.url = ""

    async def read(*args, frame, max_bytes, **kwargs):
        if max_bytes == 1024:
            return {"empty": empty}
        return {"blocks": [], "truncated": False, "truncation_reasons": []}

    reader = AsyncMock(side_effect=read)
    monkeypatch.setattr(structured, "isolated_read", reader)
    result = await structured.extract_structured(
        SimpleNamespace(main_frame=main, frames=[main, child])
    )
    assert result["partial"] is (empty is not True)
    assert result["frames"][0]["status"] == ("omitted" if empty is True else "unavailable")
    assert reader.await_count == 2


async def test_empty_metadata_probes_do_not_spend_content_slots(monkeypatch):
    main = Frame()
    empty = [Frame(main) for _ in range(3)]
    for f in empty:
        f.url = ""
    frames = [main, *empty, *[Frame(main) for _ in range(7)]]

    async def read(*args, max_bytes, **kwargs):
        if max_bytes == 1024:
            return {"empty": True}
        return {"blocks": [], "truncated": False, "truncation_reasons": []}

    reader = AsyncMock(side_effect=read)
    monkeypatch.setattr(structured, "isolated_read", reader)
    result = await structured.extract_structured(SimpleNamespace(main_frame=main, frames=frames))
    assert not result["partial"] and not result["frame_limit_reached"]
    assert sum(call.kwargs["max_bytes"] != 1024 for call in reader.await_args_list) == 8


@pytest.mark.browser
@pytest.mark.parametrize("attribute", ["title", "alt", "aria-label", "id"])
@pytest.mark.parametrize("length", [1772, 4097, 9218, 16385])
async def test_attribute_content_is_preserved_under_its_limit(attribute, length):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.set_content(
                '<main><a href="https://example.org/">Documented public robot content</a></main>'
            )
            await page.locator("a").evaluate(
                '(el, x) => el.setAttribute(x.name, "a".repeat(x.length))',
                {"name": attribute, "length": length},
            )
            value = await page.evaluate(
                structured.SCRIPT, {"include_dom": True, "text_budget": 160000}
            )
            limit = 256 if attribute == "id" else 16384 if attribute == "title" else 4096
            assert value["truncated"] is (length > limit)
            assert ("string_length" in value["truncation_reasons"]) is (length > limit)

            def find(node):
                if node["tag"] == "a":
                    return node
                for child in node.get("children", []):
                    got = find(child)
                    if got:
                        return got

            assert find(value["dom"]["root"])["attributes"][attribute] == "a" * min(length, limit)
        finally:
            await browser.close()
