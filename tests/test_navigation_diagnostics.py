import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeout

from pagequay.browser import BrowserManager
from pagequay.errors import PQError
from pagequay.navigation_diagnostics import navigation_error_details


def test_only_known_generated_goto_codes_are_exported():
    details = navigation_error_details(
        "Page.goto: net::ERR_CERT_DATE_INVALID at https://private.test/?key=SECRET\n"
        "Call log: SECRET"
    )
    assert details == {
        "cause": "TLS_CERTIFICATE_DATE_INVALID",
        "stage": "navigation",
        "browser_error": "ERR_CERT_DATE_INVALID",
    }
    assert "SECRET" not in str(details)
    for message in (
        "Page.evaluate: net::ERR_CERT_DATE_INVALID SECRET",
        "Page.goto: unknown\nCall log: net::ERR_CERT_DATE_INVALID SECRET",
        "Page.goto: net::ERR_UNKNOWN_SECRET at https://private.test/",
        "Page.goto: net::ERR_CERT_DATE_INVALIDSECRET",
    ):
        assert navigation_error_details(message) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure,expected,closed,blocked",
    [
        (
            PlaywrightError("Page.goto: net::ERR_CERT_DATE_INVALID at https://private.test/SECRET"),
            "UPSTREAM_UNAVAILABLE",
            False,
            False,
        ),
        (
            PlaywrightError("Page.goto: unknown failure SECRET"),
            "UPSTREAM_UNAVAILABLE",
            False,
            False,
        ),
        (PlaywrightTimeout("Page.goto: timed out SECRET"), "TIMEOUT", False, False),
        (
            PlaywrightError("Page.goto: net::ERR_CERT_DATE_INVALID SECRET"),
            "BROWSER_CRASHED",
            True,
            False,
        ),
        (
            PlaywrightError("Page.goto: net::ERR_CERT_DATE_INVALID SECRET"),
            "NAVIGATION_BLOCKED",
            False,
            True,
        ),
    ],
)
async def test_navigation_preserves_error_code_and_adds_only_safe_details(
    failure, expected, closed, blocked
):
    @asynccontextmanager
    async def operation(*args, **kwargs):
        yield

    page = MagicMock()
    proxy = SimpleNamespace(blocked_count=0)

    async def goto(*args, **kwargs):
        if blocked:
            proxy.blocked_count += 1
        raise failure

    page.goto = AsyncMock(side_effect=goto)
    page.is_closed.return_value = closed
    tab = SimpleNamespace(
        id="a" * 32,
        page=page,
        lock=asyncio.Lock(),
        audit=SimpleNamespace(operation=operation),
        guard_errors=[],
        network_denials=[],
        evidence=SimpleNamespace(snapshot=lambda: {}),
    )
    manager = object.__new__(BrowserManager)
    manager.db = SimpleNamespace(policy=lambda _: SimpleNamespace(navigation_timeout_seconds=1))
    manager.network_factory = lambda _: SimpleNamespace(resolve=AsyncMock())
    manager.tab = lambda *_: tab
    manager._ensure_guard = AsyncMock()
    manager.states = {"project": SimpleNamespace(blocked_navigations=set(), proxy=proxy)}
    manager.network_attestation = lambda _: {}
    request = SimpleNamespace(
        url="https://example.com/",
        allow_redirects=True,
        expected_url=None,
        respect_robots=False,
        wait_until="domcontentloaded",
    )
    job = SimpleNamespace(set_tab=lambda _: None, kind="navigate", partial_result={})
    with pytest.raises(PQError) as caught:
        await manager.navigate({"id": "project"}, request, job, tab_id=tab.id)
    error = caught.value
    assert error.code == expected
    assert "SECRET" not in error.message + str(error.details)
    if expected == "UPSTREAM_UNAVAILABLE" and "ERR_CERT_DATE_INVALID" in str(failure):
        assert error.details["cause"] == "TLS_CERTIFICATE_DATE_INVALID"
    elif expected == "TIMEOUT":
        assert error.details["stage"] == "navigation"
        assert error.details["navigation_step"] == "goto"
        assert error.details["cause"] == "PLAYWRIGHT_TIMEOUT"
        assert error.details["budget_ms"] == 1000
    else:
        assert error.details is None
