import asyncio
import json
import time
from contextlib import suppress
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from html import escape
from urllib.parse import urlsplit

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright

from .errors import PQError
from .network import EgressProxy, NetworkPolicy
from .profiles import ProfileLock, reset_directory
from .storage import uid
from .structured import extract_structured


@dataclass
class Tab:
    id: str
    page: object
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


@dataclass
class BrowserState:
    project: dict
    context: object
    profile_lock: ProfileLock
    proxy: EgressProxy
    tabs: dict = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    closing: bool = False
    blocked_navigations: set = field(default_factory=set)
    creation_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    spare_page: object = None
    headless: bool = False


async def challenge_detected(page):
    # Detection is deliberately conservative and imperfect; never solves a challenge.
    url = urlsplit(page.url)
    if url.hostname in {"google.com", "www.google.com"} and url.path.startswith("/sorry/"):
        return True
    title = (await page.title()).lower()
    text = (await page.locator("body").inner_text(timeout=3000)).lower()[:20000]
    markers = (
        "verify you are human",
        "confirm you are human",
        "unusual traffic",
        "nos systèmes ont détecté un trafic exceptionnel",
        "vérifiez que vous êtes humain",
        "checking your browser",
        "complete the captcha",
        "please complete the following challenge",
        "select all squares containing a duck",
    )
    return (
        "just a moment" in title
        or any(marker in text for marker in markers)
        or await page.locator(
            'iframe[src*="recaptcha"],iframe[src*="hcaptcha"],[data-pq-challenge="true"]'
        ).count()
        > 0
    )


class BrowserManager:
    def __init__(self, db, settings, events, artifacts, network_factory=NetworkPolicy):
        self.db, self.settings, self.events, self.artifacts = db, settings, events, artifacts
        self.network_factory = network_factory
        self.states = {}
        self.lifecycle = asyncio.Lock()
        self.playwright = None
        self.busy = lambda project_id: False

    async def start(self, project):
        async with self.lifecycle:
            return await self._start(project)

    async def _start(self, project):
        if not project["active"]:
            raise PQError("FORBIDDEN", "Project is disabled", 403)
        if project["id"] in self.states:
            return self.states[project["id"]]
        global_policy = self.db.policy()
        if len(self.states) >= global_policy.max_concurrent_browsers:
            raise PQError(
                "RATE_LIMITED",
                "Concurrent browser limit reached",
                429,
                details={
                    "scope": "browser_capacity",
                    "cause": "pagequay_capacity",
                    "retry_after_seconds": None,
                    "retry_at": None,
                },
            )
        lock = ProfileLock(self.db.root, project["id"])
        lock.acquire()
        policy = self.db.policy(project)
        network = self.network_factory(policy)
        proxy = EgressProxy(network)
        context = None
        try:
            proxy_url = await proxy.start()
            if not self.playwright:
                self.playwright = await async_playwright().start()
            context = await self.playwright.chromium.launch_persistent_context(
                str(self.db.root / "profiles" / project["id"]),
                headless=policy.headless,
                chromium_sandbox=True,
                channel=self.settings.browser_channel,
                proxy={"server": proxy_url, "bypass": "<-loopback>"},
                accept_downloads=False,
                service_workers="block",
                permissions=[],
                viewport={"width": 1280, "height": 900},
                args=[
                    "--disable-quic",
                    "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                    "--disable-background-networking",
                ],
            )
            context.set_default_timeout(policy.navigation_timeout_seconds * 1000)
            state = BrowserState(project, context, lock, proxy, headless=policy.headless)

            async def guard(route):
                try:
                    await network.resolve(route.request.url)
                    await route.continue_()
                except PQError:
                    if route.request.is_navigation_request():
                        state.blocked_navigations.add(route.request.frame.page)
                    await route.abort("blockedbyclient")
                except PlaywrightError:
                    pass

            await context.route("**/*", guard)

            async def block_websocket(ws):
                await ws.close()

            await context.route_web_socket("**/*", block_websocket)
            context.on("page", lambda page: self._register(state, page))
            context.on("close", lambda _: self._closed(state))
            for page in context.pages:
                if page.url == "about:blank" and state.spare_page is None:
                    state.spare_page = page
                else:
                    self._register(state, page)
            if policy.browser_start_minimized and not state.headless:
                await self._set_windows(state, "minimized")
            self.states[project["id"]] = state
            self.events.emit(project, "browser.started")
            self.db.audit("browser.started", project["id"])
            return state
        except BaseException as exc:
            try:
                if context:
                    with suppress(PlaywrightError):
                        await context.close()
                await proxy.close()
            finally:
                lock.release()
            if not isinstance(exc, Exception):
                raise
            if isinstance(exc, PQError):
                raise
            raise PQError(
                "BROWSER_CRASHED", "Browser start failed; run scripts/doctor.sh", 503
            ) from exc

    def _register(self, state, page):
        if any(tab.page is page for tab in state.tabs.values()):
            return
        if len(state.tabs) >= self.db.policy(state.project).max_tabs_per_project:
            asyncio.create_task(page.close())
            return
        tab = Tab(uid(), page)
        state.tabs[tab.id] = tab
        page.on("dialog", lambda dialog: asyncio.create_task(dialog.dismiss()))
        page.on("download", lambda download: asyncio.create_task(download.cancel()))
        page.on("filechooser", lambda chooser: asyncio.create_task(chooser.set_files([])))
        page.on("close", lambda _: self._tab_closed(state, tab.id))
        page.on(
            "crash", lambda _: self.events.emit(state.project, "browser.crashed", tab_id=tab.id)
        )

    def _tab_closed(self, state, tab_id):
        state.tabs.pop(tab_id, None)
        self.events.emit(state.project, "tab.closed", tab_id=tab_id)

    def _closed(self, state):
        if not state.closing:
            self.states.pop(state.project["id"], None)
            state.profile_lock.release()
            asyncio.create_task(state.proxy.close())
            self.events.emit(state.project, "browser.crashed")
            self.db.audit("browser.crashed", state.project["id"], status="error")

    async def stop(self, project, *, force=False):
        async with self.lifecycle:
            await self._stop(project, force=force)

    async def _stop(self, project, force=False):
        if not force and self.busy(project["id"]):
            raise PQError("CONFLICT", "Wait for active/queued jobs to drain", 409)
        state = self.states.get(project["id"])
        if state:
            state.closing = True
            try:
                await state.proxy.close()
                await state.context.close()
            finally:
                await state.proxy.close()
                state.profile_lock.release()
                self.states.pop(project["id"], None)
            self.events.emit(project, "browser.stopped")
            self.db.audit("browser.stopped", project["id"])

    async def restart(self, project):
        async with self.lifecycle:
            await self._stop(project)
            return await self._start(project)

    async def reset(self, project):
        async with self.lifecycle:
            await self._stop(project)
            lock = ProfileLock(self.db.root, project["id"])
            lock.acquire()
            try:
                reset_directory(self.db.root, project["id"])
                self.db.execute(
                    "UPDATE projects SET last_reset=? WHERE id=?", (time.time(), project["id"])
                )
                self.db.audit("profile.reset", project["id"])
            finally:
                lock.release()

    async def state(self, project):
        if project["id"] not in self.states and not self.db.policy(project).browser_start_on_demand:
            raise PQError("CONFLICT", "Start this browser in the administration panel", 409)
        return await self.start(project)

    def tab(self, project, tab_id):
        state = self.states.get(project["id"])
        tab = state.tabs.get(tab_id) if state else None
        if not tab or tab.page.is_closed():
            raise PQError("NOT_FOUND", "Tab not found in this project", 404)
        state.last_used = time.time()
        self.db.execute(
            "UPDATE projects SET last_activity=? WHERE id=?", (time.time(), project["id"])
        )
        return tab

    def list_tabs(self, project):
        state = self.states.get(project["id"])
        return (
            [{"tab_id": tab.id, "url": tab.page.url} for tab in state.tabs.values()]
            if state
            else []
        )

    def update_network_policies(self):
        for state in self.states.values():
            state.proxy.policy.policy = self.db.policy(state.project)

    async def close_tab(self, project, tab_id):
        tab = self.tab(project, tab_id)
        if tab.lock.locked():
            raise PQError("CONFLICT", "Tab operation is running", 409)
        await tab.page.close()

    async def _window(self, state, page, window_state=None):
        session = await state.context.new_cdp_session(page)
        try:
            window = await session.send("Browser.getWindowForTarget")
            if window_state is not None:
                await session.send(
                    "Browser.setWindowBounds",
                    {"windowId": window["windowId"], "bounds": {"windowState": window_state}},
                )
                # Native macOS minimize/restore animations complete after the CDP reply.
                async with asyncio.timeout(5):
                    while True:
                        result = await session.send(
                            "Browser.getWindowBounds", {"windowId": window["windowId"]}
                        )
                        window["bounds"] = result["bounds"]
                        if window["bounds"]["windowState"] == window_state:
                            break
                        await asyncio.sleep(0.05)
            return window
        finally:
            with suppress(PlaywrightError):
                await session.detach()

    async def _set_windows(self, state, window_state):
        seen = set()
        for page in state.context.pages:
            if page.is_closed():
                continue
            window = await self._window(state, page)
            if window["windowId"] not in seen:
                await self._window(state, page, window_state)
                seen.add(window["windowId"])

    async def window_control(self, project, *, minimized):
        async with self.lifecycle:
            state = self.states.get(project["id"])
            if state is None:
                raise PQError("CONFLICT", "Démarrez d’abord le navigateur de ce projet.", 409)
            if state.headless:
                raise PQError("CONFLICT", "Le mode sans interface n’a pas de fenêtre.", 409)
            async with state.creation_lock:
                try:
                    await self._set_windows(state, "minimized" if minimized else "normal")
                except (PlaywrightError, TimeoutError) as exc:
                    raise PQError(
                        "UPSTREAM_UNAVAILABLE", "Impossible de modifier les fenêtres.", 502
                    ) from exc
            self.db.audit("browser.minimized" if minimized else "browser.restored", project["id"])

    async def new_tab(self, project):
        state = await self.state(project)
        async with state.creation_lock:
            state.last_used = time.time()
            self.db.execute(
                "UPDATE projects SET last_activity=? WHERE id=?", (state.last_used, project["id"])
            )
            if len(state.tabs) >= self.db.policy(project).max_tabs_per_project:
                raise PQError(
                    "RATE_LIMITED",
                    "Tab limit reached",
                    429,
                    details={
                        "scope": "project_tabs",
                        "cause": "pagequay_capacity",
                        "retry_after_seconds": None,
                        "retry_at": None,
                    },
                )
            if state.spare_page is not None and not state.spare_page.is_closed():
                page, state.spare_page = state.spare_page, None
            else:
                # Chromium restores minimized windows when Playwright creates a tab.
                # Remember actual native state, including minimization from the macOS Dock.
                minimized = {}
                if not state.headless:
                    for existing in state.context.pages:
                        if not existing.is_closed():
                            window = await self._window(state, existing)
                            if window["bounds"]["windowState"] == "minimized":
                                minimized[window["windowId"]] = existing
                try:
                    page = await state.context.new_page()
                finally:
                    for existing in minimized.values():
                        if not existing.is_closed():
                            await self._window(state, existing, "minimized")
            self._register(state, page)
            tab = next((tab for tab in state.tabs.values() if tab.page is page), None)
            if tab is None:
                raise PQError("RATE_LIMITED", "Tab limit reached", 429)
            return tab

    async def human_guard(self, project, tab, job):
        while await challenge_detected(tab.page):
            if not job:
                raise PQError("CHALLENGE_REQUIRED", "Manual intervention required", 409)
            capture = None
            with suppress(PlaywrightError, PQError):
                capture = self.artifacts.put(
                    project,
                    await self._screenshot(project, tab.page),
                    "image/png",
                    "screenshot:read",
                )
            await job.wait_for_human(tab.id, capture)

    async def navigate(self, project, request, job, tab_id=None):
        await self.network_factory(self.db.policy(project)).resolve(request.url)
        tab = self.tab(project, tab_id) if tab_id else await self.new_tab(project)
        job.set_tab(tab.id)
        async with tab.lock:
            try:
                state = self.states[project["id"]]
                state.blocked_navigations.discard(tab.page)
                blocked_before = state.proxy.blocked_count
                response = await tab.page.goto(
                    request.url,
                    wait_until=request.wait_until,
                    timeout=self.db.policy(project).navigation_timeout_seconds * 1000,
                )
                await self.human_guard(project, tab, job)
                self._upstream_limit(response)
                self.events.emit(project, "tab.navigated", tab_id=tab.id)
                return {"tab_id": tab.id, "url": tab.page.url, "title": await tab.page.title()}
            except PlaywrightTimeout as exc:
                raise PQError("TIMEOUT", "Navigation timed out", 504) from exc
            except PlaywrightError as exc:
                blocked = (
                    tab.page in state.blocked_navigations
                    or state.proxy.blocked_count > blocked_before
                )
                code = (
                    "NAVIGATION_BLOCKED"
                    if blocked
                    else ("BROWSER_CRASHED" if tab.page.is_closed() else "UPSTREAM_UNAVAILABLE")
                )
                raise PQError(code, "Navigation failed", 502) from exc

    def _upstream_limit(self, response):
        if response is None or response.status != 429:
            return
        raw = response.headers.get("retry-after", "")
        retry_at, seconds = None, None
        try:
            if raw.isdigit():
                seconds = min(int(raw), 86400)
                retry_at = time.time() + seconds
            elif raw:
                retry_at = parsedate_to_datetime(raw).timestamp()
                seconds = max(0, int(retry_at - time.time()) + 1)
        except (ValueError, TypeError, OverflowError):
            pass
        raise PQError(
            "RATE_LIMITED",
            "Upstream server returned HTTP 429",
            429,
            details={
                "scope": "upstream_engine",
                "cause": "upstream_http_429",
                "retry_after_seconds": seconds,
                "retry_at": retry_at,
            },
        )

    async def submit_search_form(self, project, tab_id, form, job):
        """Submit only a server-captured engine form through the guarded browser transport."""
        await self.network_factory(self.db.policy(project)).resolve(form["url"])
        tab = self.tab(project, tab_id)
        job.set_tab(tab_id)
        timeout = self.db.policy(project).navigation_timeout_seconds * 1000
        fields = "".join(
            f'<input type="hidden" name="{escape(name, quote=True)}" '
            f'value="{escape(value, quote=True)}">'
            for name, value in form["fields"]
        )
        html = (
            f'<form id="pq-search-next" action="{escape(form["url"], quote=True)}" '
            f'method="{form["method"]}">{fields}<button type="submit">Next</button></form>'
        )
        async with tab.lock:
            await tab.page.set_content(html, wait_until="domcontentloaded", timeout=timeout)
            async with tab.page.expect_navigation(
                wait_until="domcontentloaded", timeout=timeout
            ) as nav:
                await tab.page.locator("#pq-search-next button").click(timeout=timeout)
            response = await nav.value
            await self.human_guard(project, tab, job)
            self._upstream_limit(response)

    async def actions(self, project, tab_id, request, job):
        tab = self.tab(project, tab_id)
        job.set_tab(tab_id)
        async with tab.lock:
            await self.human_guard(project, tab, job)
            for action in request.actions:
                job.check_authorization()
                await self.human_guard(project, tab, job)
                if action.selector and any(
                    s in action.selector.lower() for s in ("captcha", "turnstile")
                ):
                    raise PQError("FORBIDDEN", "Challenge interactions are not allowed", 403)
                locator = tab.page.locator(action.selector) if action.selector else None
                if action.type not in {"scroll", "wait_for_navigation"} and locator is None:
                    raise PQError("INVALID_INPUT", "Selector required")
                if action.type == "click":
                    text = await locator.evaluate(
                        "el => [el.innerText, el.getAttribute('aria-label'),"
                        "el.closest('[data-sitekey],[class*=captcha]')?.innerText]"
                        ".filter(Boolean).join(' ').toLowerCase()"
                    )
                    if any(
                        marker in text
                        for marker in (
                            "i am not a robot",
                            "i'm not a robot",
                            "i’m not a robot",
                            "je ne suis pas un robot",
                            "i am human",
                            "i'm human",
                            "captcha",
                        )
                    ):
                        raise PQError("FORBIDDEN", "Human verification cannot be automated", 403)
                    await locator.click(timeout=action.timeout_ms)
                elif action.type == "fill":
                    if action.value is None:
                        raise PQError("INVALID_INPUT", "Value required")
                    await locator.fill(action.value, timeout=action.timeout_ms)
                elif action.type == "select":
                    await locator.select_option(action.value or "", timeout=action.timeout_ms)
                elif action.type == "scroll":
                    await tab.page.mouse.wheel(action.x, action.y)
                elif action.type == "wait_for_selector":
                    await locator.wait_for(timeout=action.timeout_ms)
                else:
                    # Wait for the current navigation's load event, bounded; no arbitrary code.
                    await tab.page.wait_for_load_state(
                        "domcontentloaded", timeout=action.timeout_ms
                    )
            await self.human_guard(project, tab, job)
            return {"tab_id": tab_id, "url": tab.page.url}

    async def extract(self, project, tab_id, format, job, *, include_dom=False):
        tab = self.tab(project, tab_id)
        job.set_tab(tab_id)
        async with tab.lock:
            await self.human_guard(project, tab, job)
            if format == "structured":
                snapshot = await extract_structured(
                    tab.page,
                    include_dom=include_dom,
                    max_bytes=self.settings.max_content_bytes,
                    check=job.check_authorization,
                )
                data, media = (
                    json.dumps(snapshot, ensure_ascii=False, allow_nan=False),
                    "application/json",
                )
            elif format == "html":
                data, media = await tab.page.content(), "text/html"
            elif format == "text":
                data, media = await tab.page.locator("body").inner_text(), "text/plain"
            elif format == "links":
                # Fixed server-owned extraction, never caller-supplied JavaScript.
                data = await tab.page.locator("a[href]").evaluate_all(
                    "els => els.slice(0,1000).map(e => "
                    "({text:e.innerText.slice(0,500),url:e.href}))"
                )
                data, media = json.dumps(data), "application/json"
            else:
                metas = await tab.page.locator("meta[name],meta[property]").evaluate_all(
                    "els => els.slice(0,100).map(e => ({name:e.name||e.getAttribute('property'),"
                    "content:e.content.slice(0,2000)}))"
                )
                data = json.dumps(
                    {"title": await tab.page.title(), "url": tab.page.url, "meta": metas}
                )
                media = "application/json"
            return self.artifacts.put(project, data.encode(), media)

    async def _screenshot(self, project, page):
        state = self.states[project["id"]]
        if state.headless:
            return await page.screenshot(full_page=False)
        async with state.creation_lock:
            window = await self._window(state, page)
            minimized = window["bounds"]["windowState"] == "minimized"
            # macOS suspends the repaint required for screenshots in minimized windows.
            # Restore only for the capture, then put the window back even on cancellation.
            if minimized:
                await self._window(state, page, "normal")
            try:
                return await page.screenshot(full_page=False)
            finally:
                if minimized and not page.is_closed():
                    with suppress(PlaywrightError, TimeoutError):
                        await self._window(state, page, "minimized")

    async def screenshot(self, project, tab_id, job):
        tab = self.tab(project, tab_id)
        job.set_tab(tab_id)
        async with tab.lock:
            return self.artifacts.put(
                project, await self._screenshot(project, tab.page), "image/png", "screenshot:read"
            )

    async def shutdown(self):
        for state in list(self.states.values()):
            await self.stop(state.project, force=True)
        if self.playwright:
            await self.playwright.stop()
