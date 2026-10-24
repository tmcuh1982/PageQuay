"""Régression Greenfield : conteneurs de mise en page, sémantique et bornes."""

import json
import os

import pytest
from playwright.async_api import async_playwright

from pagequay.structured import extract_structured

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(os.environ.get("PQ_BROWSER_TESTS") != "1", reason="Use --browser"),
]


def nested(tag, count, text, attrs=""):
    return f"<{tag}{attrs}>" * count + text + f"</{tag}>" * count


@pytest.fixture
async def page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.route("**/*", lambda route: route.abort())
            yield page
        finally:
            await browser.close()


@pytest.mark.parametrize("include_dom", [False, True])
async def test_layout_depth_recovers_greenfield_text_with_provenance(page, include_dom):
    content = "<p>Public agronomic evidence <span><strong>Visible deep text</strong></span></p>"
    await page.set_content(nested("div", 35, content, ' class="layout" data-layout="section"'))
    doc = await extract_structured(page, include_dom=include_dom)
    assert doc["partial"] is False and doc["truncated"] is False
    assert doc["truncation_reasons"] == []
    assert "Visible deep text" in json.dumps(doc["blocks"])
    assert doc["blocks"][0]["provenance"] == {"xpath": None, "xpath_reason": "depth_limit"}
    assert ("dom" in doc) is include_dom


@pytest.mark.parametrize("attrs", [' role="region"', ' aria-label="Region"'])
async def test_deep_semantic_divs_still_fail(page, attrs):
    await page.set_content(nested("div", 32, "Semantic limit", attrs))
    doc = await extract_structured(page)
    assert doc["partial"] is True and doc["truncation_reasons"] == ["depth"]


async def test_physical_depth_and_privacy_remain_bounded(page):
    content = '<p>Visible</p><p hidden>HIDDEN-SECRET</p><input value="INPUT-SECRET">'
    await page.set_content(nested("div", 35, content) + nested("div", 40, "Too deep"))
    doc = await extract_structured(page, include_dom=True)
    serialized = json.dumps(doc)
    assert doc["partial"] is True and "depth" in doc["truncation_reasons"]
    assert "Visible" in serialized and "SECRET" not in serialized and "Too deep" not in serialized
    assert doc["stats"]["nodes_visited"] <= 8000
