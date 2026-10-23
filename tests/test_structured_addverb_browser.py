"""Régressions de l’export sémantique Addverb, sans accès réseau."""

import json
import os

import pytest
from playwright.async_api import async_playwright

from pagequay.structured import extract_structured

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(os.environ.get("PQ_BROWSER_TESTS") != "1", reason="Use --browser"),
]


@pytest.fixture
async def page():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.route("**/*", lambda route: route.abort())
            yield page
        finally:
            await browser.close()


@pytest.mark.parametrize("empty", ["", "   \n\t"])
async def test_empty_jsonld_placeholder_does_not_hide_valid_metadata(page, empty):
    await page.set_content(
        '<script type="application/ld+json">{"@type":"Organization","name":"Addverb"}</script>'
        + '<script type="application/ld+json" src="https://example.org/placeholder.js">'
        + empty
        + "</script><p>Public content</p>"
    )
    doc = await extract_structured(page)
    assert not doc["partial"]
    assert doc["truncation_reasons"] == []
    assert doc["metadata"]["json_ld"] == [{"@type": "Organization", "name": "Addverb"}]


@pytest.mark.parametrize("include_dom", [False, True])
async def test_long_class_only_consumes_budget_when_exported(page, include_dom):
    await page.set_content('<div class="' + "x" * 268 + '"><p>Public content</p></div>')
    doc = await extract_structured(page, include_dom=include_dom)
    assert doc["partial"] is include_dom
    assert doc["truncation_reasons"] == (["string_length"] if include_dom else [])
    assert "Public content" in json.dumps(doc["blocks"])
    if include_dom:
        assert "x" * 256 in json.dumps(doc["dom"])
    else:
        assert "dom" not in doc
        await page.set_content("<div><p>Public content</p></div>")
        without_class = await extract_structured(page)
        assert doc["stats"]["characters"] == without_class["stats"]["characters"]


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        ("{broken", "invalid_json_ld"),
        (" " * 20001, "json_ld_length"),
        ('{"name":"' + "x" * 2001 + '"}', "string_length"),
    ],
)
async def test_real_jsonld_errors_remain_partial(page, body, reason):
    await page.set_content(
        '<script type="application/ld+json">' + body + "</script><p>Public content</p>"
    )
    doc = await extract_structured(page)
    assert doc["partial"]
    assert reason in doc["truncation_reasons"]


async def test_empty_jsonld_still_obeys_script_count_limit(page):
    await page.set_content('<script type="application/ld+json"></script>' * 11)
    doc = await extract_structured(page)
    assert doc["partial"]
    assert "json_ld" in doc["truncation_reasons"]
