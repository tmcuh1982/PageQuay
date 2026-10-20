"""Depth recovery preserves semantic limits, privacy, and the original DOM topology."""

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
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            # Fixtures are entirely local; do not fetch image resources or other URLs.
            await page.route("**/*", lambda route: route.abort())
            yield page
        finally:
            await browser.close()


def nested(tag, count, content, attrs=""):
    return f"<{tag}{attrs}>" * count + content + f"</{tag}>" * count


def descendants(node):
    yield node
    for child in node.get("children", []):
        yield from descendants(child)


@pytest.mark.parametrize(
    ("tag", "count", "partial"),
    [
        ("section", 31, False),
        ("section", 32, True),
        ("div", 31, False),
        ("div", 32, False),
        ("div", 34, False),
        ("div", 35, True),
    ],
)
async def test_counted_and_physical_depth_boundaries(page, tag, count, partial):
    await page.set_content(nested(tag, count, "Deep content") + "<p>Visible sibling</p>")
    doc = await extract_structured(page, include_dom=True)
    assert doc["partial"] is partial
    assert doc["truncated"] is partial
    assert doc["truncation_reasons"] == (["depth"] if partial else [])
    text = json.dumps(doc["blocks"])
    assert ("Deep content" in text) is not partial
    assert "Visible sibling" in text


@pytest.mark.parametrize("include_dom", [False, True])
async def test_gallery_image_at_depth_35_and_sibling_credits(page, include_dom):
    gallery = nested(
        "div",
        33,
        '<picture><source type="image/png"><img src="https://example.org/logo.png" '
        'alt="agri.png"></picture>',
        ' class="layout" data-layout="gallery"',
    )
    await page.set_content(gallery + gallery)
    doc = await extract_structured(page, include_dom=include_dom)
    assert not doc["partial"] and not doc["truncated"]
    assert doc["truncation_reasons"] == []
    assert [image["alt"] for image in doc["images"]] == ["agri.png", "agri.png"]
    assert doc["stats"]["nodes_included"] == 1 + 2 * 36
    if include_dom:
        nodes = list(descendants(doc["dom"]["root"]))
        assert sum(node["tag"] == "div" for node in nodes) == 66
        assert all(
            node["provenance"] == {"xpath": None, "xpath_reason": "depth_limit"}
            for node in nodes
            if node["tag"] == "img"
        )
    else:
        assert "dom" not in doc


@pytest.mark.parametrize(
    "attrs",
    [
        ' role="region"',
        ' aria-label="Region"',
        ' aria-live="polite"',
        ' title="Label"',
        ' lang="fr"',
        ' tabindex="-1"',
        ' contenteditable="true"',
        ' onclick="void 0"',
    ],
)
async def test_semantic_or_interactive_divs_do_not_receive_credit(page, attrs):
    await page.set_content(nested("div", 32, "Beyond semantic depth", attrs))
    doc = await extract_structured(page)
    assert doc["partial"] and doc["truncation_reasons"] == ["depth"]
    assert "Beyond semantic depth" not in json.dumps(doc["blocks"])


async def test_shadow_host_and_projected_span_do_not_receive_credit(page):
    await page.set_content(
        nested("section", 29, '<div id="host"><span id="projected">Projected content</span></div>')
    )
    await page.evaluate(
        "document.querySelector('#host').attachShadow({mode:'open'}).innerHTML='<slot></slot>'"
    )
    doc = await extract_structured(page, include_dom=True)
    assert doc["partial"] and doc["truncation_reasons"] == ["depth"]
    assert doc["stats"]["open_shadow_roots"] == 1
    assert not any(
        node.get("attributes", {}).get("id") == "projected"
        for node in descendants(doc["dom"]["root"])
    )


async def test_recovered_branch_still_excludes_private_content(page):
    content = (
        "<span>Public content</span><span hidden>HIDDEN-SECRET</span>"
        '<span aria-hidden="true">ARIA-SECRET</span><script>/* SCRIPT-SECRET */</script>'
        '<input value="INPUT-SECRET"><textarea>TEXTAREA-SECRET</textarea>'
    )
    await page.set_content(nested("div", 32, content))
    doc = await extract_structured(page, include_dom=True)
    serialized = json.dumps(doc)
    assert not doc["partial"]
    assert "Public content" in serialized
    assert "SECRET" not in serialized
    assert len(doc["controls"]) == 2


@pytest.mark.parametrize("tag", ["span", "picture"])
async def test_other_neutral_envelopes_can_recover_an_image(page, tag):
    await page.set_content(nested("section", 31, f'<{tag}><img alt="Recovered"></{tag}>'))
    doc = await extract_structured(page)
    assert not doc["partial"]
    assert doc["images"][0]["alt"] == "Recovered"


async def test_recovered_text_still_consumes_shared_text_budget(page):
    await page.set_content(nested("div", 33, "x" * 2000))
    doc = await extract_structured(page, max_bytes=12_800)
    assert doc["partial"] and doc["truncation_reasons"] == ["text_budget"]
    assert doc["stats"]["characters"] == 1600


async def test_recovered_children_still_consume_node_budget(page):
    await page.set_content(nested("div", 32, "<span>Public</span>" * 5000))
    doc = await extract_structured(page)
    assert doc["partial"] and "nodes" in doc["truncation_reasons"]
    assert "depth" not in doc["truncation_reasons"]
    assert doc["stats"]["nodes_visited"] == 8000
