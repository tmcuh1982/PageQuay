import asyncio
import os
import time
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from pagequay.browser import BrowserManager, Tab
from pagequay.errors import PQError
from pagequay.jobs import Job


def challenge_fixture(monkeypatch, state="human"):
    manager = object.__new__(BrowserManager)
    manager.db = SimpleNamespace(audit=Mock())
    manager.artifacts = SimpleNamespace(put=Mock(return_value={"id": "capture"}))
    manager._screenshot = AsyncMock(return_value=b"png")
    manager._show_challenge = AsyncMock()
    session = SimpleNamespace(send=AsyncMock(), detach=AsyncMock())
    page = SimpleNamespace(
        context=SimpleNamespace(new_cdp_session=AsyncMock(return_value=session)),
        close=AsyncMock(),
    )
    tab = Tab("tab", page, evidence=SimpleNamespace(snapshot=lambda: {}))
    detector = AsyncMock(return_value=state)
    monkeypatch.setattr("pagequay.browser.challenge_state", detector)
    job = SimpleNamespace(kind="navigate", check_authorization=Mock())
    return manager, tab, job, session, detector


@pytest.mark.parametrize("failure", [PQError("TIMEOUT", "expired"), asyncio.CancelledError()])
async def test_abandoned_captcha_suspends_renderer_and_can_be_reactivated(monkeypatch, failure):
    manager, tab, job, session, _ = challenge_fixture(monkeypatch)
    job.wait_for_human = AsyncMock(side_effect=failure)
    with pytest.raises(type(failure)):
        await manager.human_guard({"id": "project"}, tab, job, deadline=time.monotonic())
    assert tab.suspended
    assert session.send.call_args_list[0].args == ("Page.stopLoading",)
    assert session.send.call_args_list[1].args == (
        "Emulation.setScriptExecutionDisabled",
        {"value": True},
    )
    assert session.send.call_args_list[2].args == ("Page.setWebLifecycleState", {"state": "frozen"})
    tab.page.close.assert_not_awaited()
    await manager._activate_tab(tab)
    assert not tab.suspended
    assert session.send.call_args.args == ("Page.setWebLifecycleState", {"state": "active"})
    assert session.detach.await_count == 1


async def test_failed_suspension_closes_only_the_challenge_tab(monkeypatch):
    manager, tab, job, session, _ = challenge_fixture(monkeypatch)
    session.send.side_effect = PlaywrightError("renderer unavailable")
    job.wait_for_human = AsyncMock(side_effect=PQError("TIMEOUT", "expired"))
    with pytest.raises(PQError, match="expired"):
        await manager.human_guard({"id": "project"}, tab, job, deadline=time.monotonic())
    tab.page.close.assert_awaited_once_with(run_before_unload=False)
    session.detach.assert_awaited_once()


async def test_repeated_unresolved_resumes_reuse_capture_and_yield(monkeypatch):
    manager, tab, job, _, detector = challenge_fixture(monkeypatch)
    detector.side_effect = ["human", "human", None]
    job.wait_for_human = AsyncMock()
    before = time.monotonic()
    await manager.human_guard({"id": "project"}, tab, job, deadline=before)
    assert time.monotonic() - before >= 0.5
    assert job.wait_for_human.await_count == 2
    manager._screenshot.assert_awaited_once()
    manager._show_challenge.assert_awaited_once()
    manager.artifacts.put.assert_called_once()
    assert not tab.suspended


@pytest.mark.parametrize("window_state", ["minimized", "normal", "maximized"])
async def test_captcha_restores_minimized_window_then_activates_tab(window_state):
    manager = object.__new__(BrowserManager)
    state = SimpleNamespace(headless=False, creation_lock=asyncio.Lock())
    manager.states = {"project": state}
    manager._window = AsyncMock(return_value={"bounds": {"windowState": window_state}})
    page = SimpleNamespace(bring_to_front=AsyncMock())
    tab = Tab("tab", page)
    await manager._show_challenge({"id": "project"}, tab)
    assert manager._window.await_count == (2 if window_state == "minimized" else 1)
    if window_state == "minimized":
        assert manager._window.call_args.args == (state, page, "normal")
    page.bring_to_front.assert_awaited_once()


async def test_headless_captcha_does_not_request_a_window():
    manager = object.__new__(BrowserManager)
    manager.states = {"project": SimpleNamespace(headless=True)}
    manager._window = AsyncMock()
    tab = Tab("tab", SimpleNamespace(bring_to_front=AsyncMock()))
    await manager._show_challenge({"id": "project"}, tab)
    manager._window.assert_not_awaited()
    tab.page.bring_to_front.assert_not_awaited()


async def test_window_restore_failure_keeps_human_wait_available(monkeypatch):
    manager, tab, job, _, detector = challenge_fixture(monkeypatch)
    manager.states = {"project": SimpleNamespace(headless=False, creation_lock=asyncio.Lock())}
    manager._show_challenge = BrowserManager._show_challenge.__get__(manager)
    manager._window = AsyncMock(side_effect=TimeoutError())
    detector.side_effect = ["human", None]
    job.wait_for_human = AsyncMock()
    await manager.human_guard({"id": "project"}, tab, job, deadline=time.monotonic())
    job.wait_for_human.assert_awaited_once()
    assert not tab.suspended
    manager.db.audit.assert_called_once()


async def test_automatic_challenge_polls_at_most_once_per_second(monkeypatch):
    manager, tab, job, _, detector = challenge_fixture(monkeypatch, "automatic")
    job.wait_for_human = AsyncMock(side_effect=PQError("TIMEOUT", "expired"))
    with pytest.raises(PQError):
        await manager.human_guard({"id": "project"}, tab, job, deadline=time.monotonic() + 0.15)
    assert detector.await_count == 2
    assert tab.suspended


async def test_human_deadline_is_shared_across_resumes():
    manager = SimpleNamespace(settings=SimpleNamespace(human_timeout_seconds=600))
    job = Job(manager, {}, None, "navigate", "browser:read")
    job.check_authorization = Mock()
    job.update = Mock()
    manager.events = SimpleNamespace(emit=Mock())
    job.human_deadline = asyncio.get_running_loop().time() + 0.1
    original_deadline = job.human_deadline
    first = asyncio.create_task(job.wait_for_human("tab", None))
    await asyncio.sleep(0)
    job.resume.set()
    await first
    with pytest.raises(PQError, match="Human intervention timed out"):
        await job.wait_for_human("tab", None)
    assert job.human_deadline == original_deadline


async def test_window_deadline_includes_initial_cdp_attachment(monkeypatch):
    manager = object.__new__(BrowserManager)

    async def stalled(*args):
        await asyncio.Event().wait()

    attach = AsyncMock(side_effect=stalled)
    page = SimpleNamespace(context=SimpleNamespace(new_cdp_session=attach))
    timeout = asyncio.timeout
    monkeypatch.setattr("pagequay.browser.asyncio.timeout", lambda _: timeout(0.02))
    with pytest.raises(TimeoutError):
        await manager._window(page, page)
    attach.assert_awaited_once()


async def test_flapping_challenge_cannot_recapture_forever(monkeypatch):
    manager, tab, job, _, _ = challenge_fixture(monkeypatch)
    tab.page.url = "https://example.org/"
    tab.evidence.checkpoint = Mock(return_value=(None, None, None, tab.page.url))
    tab.evidence.verify = Mock()

    @asynccontextmanager
    async def operation(*args, **kwargs):
        yield

    tab.audit = SimpleNamespace(operation=operation)
    manager.tab = Mock(return_value=tab)
    manager.db.policy = Mock(return_value=SimpleNamespace(navigation_timeout_seconds=30))
    manager.settings = SimpleNamespace(max_content_bytes=1024)
    manager.human_guard = AsyncMock()
    job.set_tab = Mock()
    job.request_id = None
    job.id = "job"
    reader = AsyncMock(return_value="discarded")
    monkeypatch.setattr("pagequay.browser.read_page", reader)
    monkeypatch.setattr("pagequay.browser.challenge_detected", AsyncMock(return_value=True))
    with pytest.raises(PQError, match="did not stabilize"):
        await manager.extract({"id": "project"}, tab.id, "text", job)
    assert reader.await_count == 3
    manager.artifacts.put.assert_not_called()
    assert tab.suspended


@pytest.mark.browser
@pytest.mark.skipif(os.environ.get("PQ_BROWSER_TESTS") != "1", reason="Use --browser")
async def test_real_challenge_timer_stops_after_cancel_and_restarts_on_activation():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.set_content(
                "<p>Verify you are human</p>"
                "<script>window.ticks=0; setInterval(()=>window.ticks++, 10)</script>"
            )
            manager = object.__new__(BrowserManager)
            manager.states = {}
            manager.db = SimpleNamespace(audit=Mock())
            tab = Tab("tab", page, evidence=SimpleNamespace(snapshot=lambda: {}))
            job = SimpleNamespace(
                kind="download_image",
                check_authorization=Mock(),
                wait_for_human=AsyncMock(side_effect=asyncio.CancelledError()),
            )
            with pytest.raises(asyncio.CancelledError):
                await manager.human_guard({"id": "project"}, tab, job, deadline=time.monotonic())
            assert tab.suspended and not page.is_closed()
            ticks = await asyncio.wait_for(page.evaluate("window.ticks"), 2)
            await asyncio.sleep(0.2)
            assert await asyncio.wait_for(page.evaluate("window.ticks"), 2) == ticks
            await manager._activate_tab(tab)
            await asyncio.wait_for(page.wait_for_function("window.ticks > " + str(ticks)), 2)
            assert not tab.suspended
        finally:
            await browser.close()
