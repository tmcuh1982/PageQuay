"""Régressions Chromium locales : URL data, HTML dérivé et DOM vivant intact."""

import json

import pytest
from playwright.async_api import async_playwright

from pagequay.errors import PQError
from pagequay.page_reader import read_page
from pagequay.structured import extract_structured


@pytest.fixture
async def page():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.route("**/*", lambda route: route.abort())
            yield page
        finally:
            await browser.close()


async def test_long_inline_media_does_not_mark_structured_text_partial(page):
    await page.set_content(
        "<h1>Fixture</h1><p>Physical product facts.</p>"
        '<img src="data:image/png;base64,' + "A" * 3000 + '">'
    )
    document = await extract_structured(page)
    assert document["partial"] is False
    assert document["truncation_reasons"] == []
    assert "Physical product facts." in json.dumps(document["blocks"])


async def test_real_long_https_url_still_marks_partial(page):
    await page.set_content(
        '<h1>Fixture</h1><a href="https://example.org/' + "a" * 3000 + '">Technical document</a>'
    )
    document = await extract_structured(page)
    assert document["partial"] is True
    assert "url_length" in document["truncation_reasons"]


async def test_derived_html_keeps_all_text_and_live_dom(page):
    body = (
        "<!DOCTYPE html><html><body><h1>Fixture</h1>"
        '<p>Physical product facts.</p><img alt="Part" src="data:image/png;base64,'
        + "A" * 5000
        + '"><video src="data:video/mp4;base64,'
        + "B" * 5000
        + '"></video><a href="data:text/plain,proof">Evidence</a></body></html>'
    )
    await page.set_content(body)
    before = await page.content()
    with pytest.raises(PQError):
        await read_page(page, "html", 4000)
    result = await read_page(page, "html", 4000, omit_inline_media=True)
    assert result["derivation"]["contract"] == "html-inline-media-omission/1"
    assert result["derivation"]["removed_attribute_count"] == 2
    assert result["derivation"]["removed_characters"] > 10000
    assert len(result["html"].encode()) < 4000
    assert "Physical product facts." in result["html"]
    assert "data:text/plain,proof" in result["html"]
    assert 'alt="Part"' in result["html"]
    assert await page.content() == before


async def test_derived_html_does_not_hide_a_text_size_limit(page):
    await page.set_content("<h1>Fixture</h1><p>" + "x" * 5000 + "</p>")
    with pytest.raises(PQError):
        await read_page(page, "html", 4000, omit_inline_media=True)
