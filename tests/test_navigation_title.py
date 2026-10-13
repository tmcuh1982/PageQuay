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
