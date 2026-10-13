import json
import os

import pytest
from playwright.async_api import async_playwright

from pagequay.structured import extract_structured

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(os.environ.get("PQ_BROWSER_TESTS") != "1", reason="Use --browser"),
]


@pytest.mark.parametrize("count", [250, 350])
async def test_long_select_is_bounded_without_exporting_values(count):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        options = "".join(f'<option value="PRIVATE_VALUE">Label{i}</option>' for i in range(count))
        await page.set_content('<main><select name="country">' + options + "</select></main>")
        document = await extract_structured(page)
        select = document["controls"][0]
        assert len(select["options"]) == min(count, 300)
        assert ("options" in document["truncation_reasons"]) is (count > 300)
        assert document["partial"] is (count > 300)
        assert "PRIVATE_VALUE" not in json.dumps(document)
        await browser.close()
