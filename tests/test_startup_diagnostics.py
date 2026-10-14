import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from playwright.async_api import Error, TimeoutError, async_playwright

from pagequay.browser import BrowserManager
from pagequay.errors import PQError
from pagequay.profiles import ProfileLock
from pagequay.startup_diagnostics import startup_error_details


@pytest.mark.parametrize(
    "error,cause",
    [
        (TimeoutError("SECRET /private/profile"), "BROWSER_LAUNCH_TIMEOUT"),
        (
            Error("BrowserType.launch_persistent_context: Executable doesn't exist at /SECRET"),
            "BROWSER_EXECUTABLE_MISSING",
        ),
        (
            Error(
                "BrowserType.launch_persistent_context: Failed to launch chromium "
                "because executable doesn't exist at /SECRET"
            ),
            "BROWSER_EXECUTABLE_MISSING",
        ),
        (
            Error(
                "BrowserType.launch_persistent_context: closed\n"
                "[err] /SECRET/SingletonLock: File exists (17)"
            ),
            "BROWSER_PROFILE_LOCK_EXISTS",
        ),
        (Error("Page.goto: /SECRET/SingletonLock: File exists"), "UNKNOWN_STARTUP_FAILURE"),
        (RuntimeError("SECRET /SingletonLock: File exists"), "UNKNOWN_STARTUP_FAILURE"),
    ],
)
def test_launch_diagnostics_are_typed_and_private(error, cause):
    result = startup_error_details(error, "browser_launch")
    assert result["cause"] == cause
    assert "SECRET" not in str(result)


def test_non_launch_failure_is_not_misclassified():
    error = TimeoutError("SECRET")
    result = startup_error_details(error, "proxy_start")
    assert result["cause"] == "UNKNOWN_STARTUP_FAILURE"
    assert result["startup_step"] == "proxy_start"


@pytest.mark.asyncio
async def test_manager_launch_failure_keeps_cleanup_and_safe_details(tmp_path):
    db = SimpleNamespace(
        root=tmp_path,
        policy=lambda *args: SimpleNamespace(max_concurrent_browsers=1, headless=True),
    )
    manager = BrowserManager(
        db, SimpleNamespace(browser_channel=None), None, None, network_factory=lambda _: object()
    )
    failure = TimeoutError("SECRET")
    manager.playwright = SimpleNamespace(
        chromium=SimpleNamespace(
            executable_path="/unused", launch_persistent_context=AsyncMock(side_effect=failure)
        )
    )
    lock = MagicMock()
    proxy = SimpleNamespace(
        browser_proxy_rules=(
            "http=http://127.0.0.1:1;https=http://127.0.0.1:1;socks=http://127.0.0.1:2"
        ),
        start=AsyncMock(return_value="http://127.0.0.1:1"),
        close=AsyncMock(),
    )
    with (
        patch("pagequay.browser.ProfileLock", return_value=lock),
        patch("pagequay.browser.EgressProxy", return_value=proxy),
    ):
        with pytest.raises(PQError) as caught:
            await manager.start({"id": "fixture", "active": True})
    assert caught.value.code == "BROWSER_CRASHED"
    assert caught.value.details["cause"] == "BROWSER_LAUNCH_TIMEOUT"
    assert caught.value.details["startup_step"] == "browser_launch"
    assert "SECRET" not in caught.value.message + str(caught.value.details)
    proxy.close.assert_awaited_once()
    lock.release.assert_called_once()
    assert manager.states == {}


@pytest.mark.browser
@pytest.mark.skipif(os.environ.get("PQ_BROWSER_TESTS") != "1", reason="Requires Playwright driver")
@pytest.mark.asyncio
async def test_real_missing_executable_is_classified_and_lock_released(tmp_path):
    (tmp_path / "profiles").mkdir()
    async with async_playwright() as playwright:
        db = SimpleNamespace(
            root=tmp_path,
            policy=lambda *args: SimpleNamespace(max_concurrent_browsers=1, headless=True),
        )
        manager = BrowserManager(
            db,
            SimpleNamespace(browser_channel=None),
            None,
            None,
            network_factory=lambda _: object(),
        )
        manager.playwright = SimpleNamespace(
            chromium=SimpleNamespace(
                executable_path=str(tmp_path / "missing-browser"),
                launch_persistent_context=playwright.chromium.launch_persistent_context,
            )
        )
        proxy = SimpleNamespace(
            browser_proxy_rules=(
                "http=http://127.0.0.1:1;https=http://127.0.0.1:1;socks=http://127.0.0.1:2"
            ),
            start=AsyncMock(return_value="http://127.0.0.1:1"),
            close=AsyncMock(),
        )
        with patch("pagequay.browser.EgressProxy", return_value=proxy):
            with pytest.raises(PQError) as caught:
                await manager.start({"id": "fixture", "active": True})
        assert caught.value.details["cause"] == "BROWSER_EXECUTABLE_MISSING"
        assert str(tmp_path) not in str(caught.value.details)
        assert caught.value.details["startup_step"] == "browser_launch"
        proxy.close.assert_awaited_once()
        lock = ProfileLock(tmp_path, "fixture")
        lock.acquire()
        lock.release()
