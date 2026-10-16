"""Injection de timeouts dans navigate, sans navigateur, réseau ou profil réel."""

import asyncio
import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from playwright.async_api import TimeoutError as PlaywrightTimeout

from pagequay.browser import BrowserManager
from pagequay.errors import PQError, error_body


class NavigationTimeoutTests(unittest.IsolatedAsyncioTestCase):
    def fixture(self, step):
        @asynccontextmanager
        async def operation(*args, **kwargs):
            yield

        failure = PlaywrightTimeout("PRIVATE_URL_AND_COOKIE must never be exported")
        page = MagicMock()
        page.url = "https://example.com/redirect"
        page.goto = AsyncMock(return_value=SimpleNamespace(status=200))
        page.is_closed.return_value = False
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
        manager.human_guard = AsyncMock()
        manager.apply_cookie_policy = AsyncMock(return_value={})
        manager.navigation_title = AsyncMock(return_value={"title": "fixture"})
        manager.check_robots = AsyncMock(return_value={})
        manager.check_scope = MagicMock()
        manager._upstream_limit = MagicMock()
        manager.events = SimpleNamespace(emit=MagicMock())
        manager.states = {
            "project": SimpleNamespace(
                blocked_navigations=set(), proxy=SimpleNamespace(blocked_count=0)
            )
        }
        manager.network_attestation = lambda _: {}
        request = SimpleNamespace(
            url="https://example.com/",
            allow_redirects=True,
            expected_url=None,
            respect_robots=step == "robots_redirect",
            wait_until="domcontentloaded",
        )
        job = SimpleNamespace(set_tab=lambda _: None, kind="navigate", partial_result={})
        if step == "goto":
            page.goto.side_effect = failure
        elif step == "human_guard":
            manager.human_guard.side_effect = failure
        elif step == "robots_redirect":
            manager.check_robots.side_effect = [{}, failure]
        elif step == "cookie_consent":
            manager.apply_cookie_policy.side_effect = failure
        elif step == "title":
            manager.navigation_title.side_effect = failure
        return manager, request, job, tab, failure

    async def test_timeout_identifies_actual_phase_and_budget_without_private_text(self):
        for step in ("goto", "human_guard", "robots_redirect", "cookie_consent", "title"):
            with self.subTest(step=step):
                manager, request, job, tab, _ = self.fixture(step)
                with self.assertRaises(PQError) as caught:
                    await manager.navigate({"id": "project"}, request, job, tab_id=tab.id)
                error = caught.exception
                self.assertEqual(error.code, "TIMEOUT")
                self.assertEqual(error.status, 504)
                self.assertIsNotNone(error.details)
                self.assertEqual(error.details["stage"], "navigation")
                self.assertEqual(error.details["cause"], "PLAYWRIGHT_TIMEOUT")
                self.assertEqual(error.details["navigation_step"], step)
                self.assertEqual(error.details["budget_ms"], 1000)
                self.assertIs(type(error.details["elapsed_ms"]), int)
                self.assertGreaterEqual(error.details["elapsed_ms"], 0)
                self.assertNotIn(
                    "PRIVATE",
                    str(
                        error_body(
                            error.code, error.message, "fixture-request", details=error.details
                        )
                    ),
                )
                self.assertEqual(job.partial_result["tab_id"], tab.id)

    async def test_guard_error_keeps_priority_over_timeout(self):
        manager, request, job, tab, failure = self.fixture("goto")
        guard = PQError("NAVIGATION_BLOCKED", "Navigation blocked", 403)

        async def goto(*args, **kwargs):
            tab.guard_errors.append(guard)
            raise failure

        tab.page.goto.side_effect = goto
        with self.assertRaises(PQError) as caught:
            await manager.navigate({"id": "project"}, request, job, tab_id=tab.id)
        self.assertIs(caught.exception, guard)

    async def test_pagequay_title_timeout_is_enriched_and_existing_details_preserved(self):
        for details in (None, {"stage": "existing"}):
            manager, request, job, tab, _ = self.fixture("title")
            failure = PQError("TIMEOUT", "Navigation title budget exhausted", 504, details=details)
            manager.navigation_title.side_effect = failure
            with self.assertRaises(PQError) as caught:
                await manager.navigate({"id": "project"}, request, job, tab_id=tab.id)
            self.assertIs(caught.exception, failure)
            if details is None:
                self.assertEqual(failure.details["navigation_step"], "title")
                self.assertEqual(failure.details["cause"], "PAGEQUAY_TIMEOUT")
            else:
                self.assertIs(failure.details, details)


class TimeoutDetailsTests(unittest.TestCase):
    def test_closed_values_and_elapsed_are_explicit(self):
        from pagequay.navigation_diagnostics import navigation_timeout_details

        result = navigation_timeout_details("goto", 30, 1.234, source="playwright")
        self.assertEqual(
            result,
            {
                "stage": "navigation",
                "cause": "PLAYWRIGHT_TIMEOUT",
                "navigation_step": "goto",
                "budget_ms": 30000,
                "elapsed_ms": 1234,
            },
        )

    def test_unknown_private_values_and_nonfinite_numbers_are_not_exported(self):
        from pagequay.navigation_diagnostics import navigation_timeout_details

        for step, budget, elapsed, source in [
            ("PRIVATE_STEP", 30, 1, "playwright"),
            ("goto", True, 1, "playwright"),
            ("goto", 121, 1, "playwright"),
            ("goto", 30, float("nan"), "playwright"),
            ("goto", 30, float("inf"), "playwright"),
            ("goto", 30, -1, "playwright"),
            ("goto", 30, 86401, "playwright"),
            ("goto", 30, True, "playwright"),
            ("goto", 30, 1, "PRIVATE_SOURCE"),
        ]:
            self.assertIsNone(navigation_timeout_details(step, budget, elapsed, source=source))


if __name__ == "__main__":
    unittest.main()
