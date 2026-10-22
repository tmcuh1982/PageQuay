import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from pagequay.browser import BrowserManager
from pagequay.errors import PQError


@pytest.mark.asyncio
@pytest.mark.parametrize("cause", ["NAVIGATION_CHANGED", "scope_changed"])
async def test_title_discards_unstable_capture_but_never_scope_change(monkeypatch, cause):
    from pagequay import browser

    manager = object.__new__(BrowserManager)
    manager.human_guard = AsyncMock()
    calls = []

    def verify(checkpoint, url):
        calls.append(url)
        if len(calls) == 1:
            raise PQError(cause, "changed", 409)

    evidence = SimpleNamespace(checkpoint=lambda url: "checkpoint", verify=verify)
    tab = SimpleNamespace(
        page=SimpleNamespace(url="https://example.com/"), guard_errors=[], evidence=evidence
    )
    reader = AsyncMock(return_value={"title": "stable"})
    monkeypatch.setattr(browser, "read_title", reader)
    if cause == "scope_changed":
        with pytest.raises(PQError):
            await manager.navigation_title(
                {}, tab, None, expected_url=tab.page.url, deadline=time.monotonic() + 1
            )
        assert reader.await_count == 1
    else:
        result = await manager.navigation_title(
            {}, tab, None, expected_url=tab.page.url, deadline=time.monotonic() + 1
        )
        assert result == {"title": "stable"}
        assert reader.await_count == 2
        assert manager.human_guard.await_count == 2


@pytest.mark.asyncio
async def test_title_never_extends_navigation_deadline(monkeypatch):
    manager = object.__new__(BrowserManager)
    manager.human_guard = AsyncMock()
    with pytest.raises(PQError) as error:
        await manager.navigation_title(
            {}, None, None, expected_url=None, deadline=time.monotonic() - 1
        )
    assert error.value.code == "TIMEOUT"
    manager.human_guard.assert_not_awaited()


async def test_tab_info_rejects_title_from_changed_navigation(monkeypatch):
    import asyncio

    from pagequay.browser import Tab
    from pagequay.navigation import NavigationEvidence

    page = SimpleNamespace(
        url="https://example.org/first",
        on=lambda *args: None,
        main_frame=SimpleNamespace(url="https://example.org/first"),
    )
    tab = Tab("tab", page, lock=asyncio.Lock())
    tab.evidence = NavigationEvidence(page)
    manager = object.__new__(BrowserManager)
    manager.tab = lambda *_: tab

    async def read(_):
        page.url = page.main_frame.url = "https://example.org/second"
        tab.evidence.navigated(page.main_frame)
        return {"title": "Second document", "title_truncated": False}

    monkeypatch.setattr("pagequay.browser.read_title", read)
    with pytest.raises(PQError) as error:
        await manager.tab_info({}, "tab")
    assert error.value.code == "NAVIGATION_CHANGED"
    assert error.value.details["stage"] == "tab_info.title"
    assert error.value.details["observed_url"] == page.url
