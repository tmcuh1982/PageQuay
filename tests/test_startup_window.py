"""The real startup must survive optional minimization timeout, never a dead browser."""

import builtins
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from playwright.async_api import Error
from test_download_image import image_site as image_site

from pagequay.browser import BrowserManager
from pagequay.errors import PQError


@pytest.mark.parametrize("health_failure", [False, True])
async def test_startup_minimization_timeout_keeps_only_healthy_browser(tmp_path, health_failure):
    policy = SimpleNamespace(
        max_concurrent_browsers=1,
        headless=False,
        navigation_timeout_seconds=30,
        browser_start_minimized=True,
    )
    db = SimpleNamespace(root=tmp_path, policy=lambda *args: policy, audit=MagicMock())
    events = SimpleNamespace(emit=MagicMock())
    manager = BrowserManager(
        db, SimpleNamespace(browser_channel=None), events, None, network_factory=lambda _: object()
    )
    page = SimpleNamespace(url="about:blank", is_closed=lambda: False)
    session = SimpleNamespace(send=AsyncMock(), detach=AsyncMock())
    if health_failure:
        session.send.side_effect = Error("closed /SECRET")
    context = SimpleNamespace(
        pages=[page],
        set_default_timeout=MagicMock(),
        route=AsyncMock(),
        on=MagicMock(),
        close=AsyncMock(),
        new_cdp_session=AsyncMock(return_value=session),
    )
    manager.playwright = SimpleNamespace(
        chromium=SimpleNamespace(
            executable_path="/unused", launch_persistent_context=AsyncMock(return_value=context)
        )
    )
    lock = MagicMock()
    proxy = SimpleNamespace(
        start=AsyncMock(return_value="http://127.0.0.1:1"),
        close=AsyncMock(),
        browser_proxy_rules="http=http://127.0.0.1:1",
    )
    manager._set_windows = AsyncMock(side_effect=builtins.TimeoutError())
    with (
        patch("pagequay.browser.ProfileLock", return_value=lock),
        patch("pagequay.browser.EgressProxy", return_value=proxy),
    ):
        if health_failure:
            with pytest.raises(PQError):
                await manager.start({"id": "fixture", "active": True})
            context.close.assert_awaited_once()
            proxy.close.assert_awaited_once()
            lock.release.assert_called_once()
            assert not manager.states
        else:
            state = await manager.start({"id": "fixture", "active": True})
            assert manager.states["fixture"] is state
            context.close.assert_not_awaited()
            proxy.close.assert_not_awaited()
            lock.release.assert_not_called()
            session.send.assert_awaited_once_with("Browser.getVersion")
            session.detach.assert_awaited_once()
            db.audit.assert_any_call(
                "browser.window_state_unconfirmed",
                "fixture",
                status="warning",
                details={
                    "operation": "startup_minimize",
                    "cause": "window_bounds_timeout",
                    "browser_healthy": True,
                },
            )


async def test_timeout_continues_after_real_cdp_health_check(image_site, monkeypatch):
    rt, project, *_ = image_site
    state = await rt.browser.start(project)
    monkeypatch.setattr(rt.browser, "_set_windows", AsyncMock(side_effect=builtins.TimeoutError()))
    await rt.browser._startup_windows(state)
    assert rt.browser.states[project["id"]] is state
    assert any(not page.is_closed() for page in state.context.pages)
    if hasattr(rt.db, "telemetry"):
        await rt.db.telemetry.flush_async()
    warning = rt.db.one(
        "SELECT details FROM audit WHERE action='browser.window_state_unconfirmed' "
        "ORDER BY at DESC LIMIT 1"
    )
    assert warning is not None


async def test_automatic_window_change_does_not_wait_for_native_confirmation():
    session = SimpleNamespace(
        send=AsyncMock(
            side_effect=[
                {"windowId": 1, "bounds": {"windowState": "normal"}},
                {},
                {"bounds": {"windowState": "normal"}},
            ]
        ),
        detach=AsyncMock(),
    )
    state = SimpleNamespace(
        context=SimpleNamespace(new_cdp_session=AsyncMock(return_value=session))
    )
    manager = BrowserManager(None, None, None, None)
    result = await manager._window(state, object(), "minimized", confirm=False)
    assert result["bounds"]["windowState"] == "normal"
    assert session.send.await_count == 3
    session.detach.assert_awaited_once()


async def test_explicit_window_change_still_confirms_requested_state():
    session = SimpleNamespace(
        send=AsyncMock(
            side_effect=[
                {"windowId": 1, "bounds": {"windowState": "normal"}},
                {},
                {"bounds": {"windowState": "normal"}},
                {"bounds": {"windowState": "minimized"}},
            ]
        ),
        detach=AsyncMock(),
    )
    state = SimpleNamespace(
        context=SimpleNamespace(new_cdp_session=AsyncMock(return_value=session))
    )
    manager = BrowserManager(None, None, None, None)
    result = await manager._window(state, object(), "minimized")
    assert result["bounds"]["windowState"] == "minimized"
    assert session.send.await_count == 4
