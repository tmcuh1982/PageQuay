"""Une iframe technique aria-hidden ne rend pas la copie visible incomplète."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from pagequay.errors import PQError
from pagequay.structured import extract_structured


class Frame:
    def __init__(self, url, parent=None):
        self.url, self.parent_frame, self.name = url, parent, ""
        self.handle = SimpleNamespace(
            is_visible=AsyncMock(return_value=True),
            get_attribute=AsyncMock(return_value=None),
            dispose=AsyncMock(),
        )

    async def frame_element(self):
        return self.handle

    def is_detached(self):
        return False


@pytest.mark.parametrize("aria_hidden", ["true", "false", None])
async def test_sized_browser_error_frame_respects_dom_exclusion(monkeypatch, aria_hidden):
    main = Frame("https://example.org/manual")
    child = Frame("chrome-error://chromewebdata/", main)
    child.handle.get_attribute.return_value = aria_hidden
    page = SimpleNamespace(main_frame=main, frames=[main, child])
    read = AsyncMock(return_value={"url": main.url, "blocks": [], "truncated": False})
    monkeypatch.setattr("pagequay.structured.isolated_read", read)
    doc = await extract_structured(page)
    assert doc["frames"][0]["status"] == ("omitted" if aria_hidden == "true" else "unavailable")
    assert doc["partial"] is (aria_hidden != "true")
    assert doc["frames"][0]["reason"] == (
        "hidden_frame" if aria_hidden == "true" else "unsupported_frame_scheme"
    )
    assert read.await_count == 1
    child.handle.dispose.assert_awaited_once()


async def test_aria_hidden_http_frame_is_not_read(monkeypatch):
    main = Frame("https://example.org/manual")
    child = Frame("https://example.org/consent", main)
    child.handle.get_attribute.return_value = "true"
    read = AsyncMock(return_value={"url": main.url, "blocks": [], "truncated": False})
    monkeypatch.setattr("pagequay.structured.isolated_read", read)
    doc = await extract_structured(SimpleNamespace(main_frame=main, frames=[main, child]))
    assert doc["frames"][0]["status"] == "omitted"
    assert read.await_count == 1
    assert not doc["partial"]


async def test_main_browser_error_is_still_blocked(monkeypatch):
    main = Frame("chrome-error://chromewebdata/")
    read = AsyncMock()
    monkeypatch.setattr("pagequay.structured.isolated_read", read)
    with pytest.raises(PQError) as error:
        await extract_structured(SimpleNamespace(main_frame=main, frames=[main]))
    assert error.value.code == "NAVIGATION_BLOCKED"
    read.assert_not_awaited()
