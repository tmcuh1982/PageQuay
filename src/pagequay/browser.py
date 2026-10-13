import asyncio
import hashlib
import json
import time
from contextlib import suppress
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from html import escape
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright

from .audit import TabAudit
from .bounds import short_url
from .errors import PQError
from .frame_context import register_frame_selector
from .navigation import (
    NavigationEvidence,
    exact_error,
    redirect_guard,
    require_https,
    scope_error,
    utc_now,
)
from .network import EgressProxy, NetworkPolicy
from .page_reader import click_classification, read_page, read_title
from .profiles import ProfileLock, reset_directory
from .storage import uid
from .structured import extract_structured


@dataclass
class Tab:
    id: str
    page: object
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    audit: object = None
    evidence: object = None
    owner_key_id: str | None = None
    expected_url: str | None = None
    https_only: bool = False
    scope_url: str | None = None
    respect_robots: bool = False
    robots_url: str | None = None
    egress_guard: object = None
    guard_errors: list = field(default_factory=list)
    network_denials: list = field(default_factory=list)
    network_denials_truncated: bool = False
    robots: dict = field(default_factory=lambda: {"status": "not_checked"})


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


async def challenge_state(page, *, evidence=None):
    # Detection is deliberately conservative and imperfect; never solves a challenge.
    url = urlsplit(page.url)
    if url.hostname in {"google.com", "www.google.com"} and url.path.startswith("/sorry/"):
        return "human"
    sample = await read_page(page, "challenge", max_bytes=200000)
    title = sample["title"].lower()
    text = sample["text"].lower()
    markers = (
        "verify you are human",
        "confirm you are human",
        "unusual traffic",
        "nos systèmes ont détecté un trafic exceptionnel",
        "vérifiez que vous êtes humain",
        "complete the captcha",
        "please complete the following challenge",
        "select all squares containing a duck",
    )
    if any(marker in text for marker in markers) or sample["frame"]:
        return "human"
    if (
        (evidence is not None and evidence.cf_challenge)
        or "just a moment" in title
        or any(
            marker in text
            for marker in (
                "checking your browser",
                "verifying you are human",
                "performing security verification",
            )
        )
    ):
        return "automatic"
    return None


async def challenge_detected(page, *, evidence=None):
    return await challenge_state(page, evidence=evidence) is not None


class BrowserManager:
    def __init__(self, db, settings, events, artifacts, network_factory=NetworkPolicy):
        self.db, self.settings, self.events, self.artifacts = db, settings, events, artifacts
        self.network_factory = network_factory
        self.states = {}
        self.lifecycle = asyncio.Lock()
        self.playwright = None
        self.busy = lambda project_id: False
        self.audit_tasks = set()
        self.guard_tasks = set()

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
                await register_frame_selector(self.playwright)
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
                user_agent="PageQuay/0.2.0",
                args=[
                    "--disable-quic",
                    "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                    "--disable-background-networking",
                ],
            )
            context.set_default_timeout(policy.navigation_timeout_seconds * 1000)
            state = BrowserState(project, context, lock, proxy, headless=policy.headless)

            async def guard(route):
                tab = None
                try:
                    page = route.request.frame.page
                    tab = next((tab for tab in state.tabs.values() if tab.page is page), None)
                    if tab and tab.https_only:
                        require_https(route.request.url)
                        if route.request.frame != page.main_frame:
                            # Strict mode fails closed until OOPIF interception is fully attested.
                            raise PQError(
                                "NAVIGATION_BLOCKED",
                                "Strict subframe network is unavailable",
                                403,
                                details={"cause": "strict_subframe_network_unattested"},
                            )
                    if (
                        tab
                        and tab.expected_url
                        and route.request.is_navigation_request()
                        and route.request.frame == page.main_frame
                        and route.request.url != tab.expected_url.split("#", 1)[0]
                    ):
                        raise exact_error(route.request.url)
                    await network.resolve(route.request.url)
                    await route.continue_()
                except PQError as exc:
                    if tab is not None:
                        if len(tab.network_denials) < 32:
                            tab.network_denials.append(
                                {
                                    "code": exc.code,
                                    "cause": (exc.details or {}).get("cause", exc.code),
                                    "main_document": route.request.frame == page.main_frame,
                                }
                            )
                        else:
                            tab.network_denials_truncated = True
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
        tab.evidence = NavigationEvidence(page)
        tab.audit = TabAudit(self.db, state.project, tab, self.audit_tasks)
        state.tabs[tab.id] = tab
        page.on("dialog", lambda dialog: asyncio.create_task(dialog.dismiss()))
        page.on("download", lambda download: asyncio.create_task(download.cancel()))
        page.on("filechooser", lambda chooser: asyncio.create_task(chooser.set_files([])))
        page.on("close", lambda _: self._tab_closed(state, tab.id))
        page.on(
            "crash", lambda _: self.events.emit(state.project, "browser.crashed", tab_id=tab.id)
        )

    async def _release_guard(self, tab):
        if tab.egress_guard is not None:
            guard, tab.egress_guard = tab.egress_guard, None
            await guard.__aexit__(None, None, None)

    async def _ensure_guard(self, project, tab):
        if tab.egress_guard is None:
            guard = redirect_guard(tab.page, self.states[project["id"]].proxy.policy, contract=tab)
            tab.guard_errors = await guard.__aenter__()
            tab.egress_guard = guard

    def _tab_closed(self, state, tab_id):
        tab = state.tabs.pop(tab_id, None)
        if tab is not None and tab.egress_guard is not None:
            task = asyncio.create_task(self._release_guard(tab))
            self.guard_tasks.add(task)
            task.add_done_callback(self.guard_tasks.discard)
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
                for tab in list(state.tabs.values()):
                    await self._release_guard(tab)
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
            [{"tab_id": tab.id, "url": short_url(tab.page.url)} for tab in state.tabs.values()]
            if state
            else []
        )

    def update_network_policies(self):
        for state in self.states.values():
            state.proxy.policy.policy = self.db.policy(state.project)

    async def close_tab(self, project, tab_id, *, key_id=None):
        tab = self.tab(project, tab_id)
        if key_id is not None and tab.owner_key_id is not None and key_id != tab.owner_key_id:
            raise PQError("FORBIDDEN", "Only the originating key may close this tab", 403)
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

    async def new_tab(self, project, *, tab_id=None, owner_key_id=None):
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
            if tab_id is not None and tab.id != tab_id:
                state.tabs.pop(tab.id)
                tab.id = tab_id
                state.tabs[tab.id] = tab
            tab.owner_key_id = owner_key_id
            return tab

    async def check_robots(self, project, url, job):
        # A dedicated, owned tab goes through the same egress controls, then is closed.
        parts = urlsplit(url)
        robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
        helper = await self.new_tab(project, owner_key_id=job.key_id)
        helper.expected_url = robots_url
        helper.https_only = parts.scheme == "https"
        try:
            network = self.network_factory(self.db.policy(project))
            async with redirect_guard(
                helper.page,
                network,
                expected_url=robots_url,
                allow_redirects=False,
                https_only=helper.https_only,
            ) as errors:
                response = await helper.page.goto(
                    robots_url,
                    wait_until="domcontentloaded",
                    timeout=self.db.policy(project).navigation_timeout_seconds * 1000,
                )
                if errors:
                    raise errors[0]
                if response is None:
                    raise PQError("ROBOTS_UNAVAILABLE", "Robots HTTP status unknown", 503)
                evidence = {
                    "status": "checked",
                    "url": robots_url,
                    "http_status": response.status,
                    "observed_at": utc_now(),
                    "content_type": response.headers.get("content-type", "")[:256],
                    "user_agent": "PageQuay/0.2.0",
                }
                self._upstream_limit(response)
                if response.status in {401, 403}:
                    raise PQError(
                        "ROBOTS_DENIED", "Robots access explicitly refused", 403, details=evidence
                    )
                if response.status in {404, 410}:
                    return {**evidence, "allowed": True, "basis": "robots_not_found"}
                if await challenge_detected(helper.page, evidence=helper.evidence):
                    await self.human_guard(project, helper, job)
                    raise PQError(
                        "ROBOTS_UNAVAILABLE",
                        "Robots changed after human intervention; "
                        "explicit new acquisition required",
                        503,
                    )
                if response.status != 200:
                    raise PQError("ROBOTS_UNAVAILABLE", "Robots unavailable", 503)
                if not response.headers.get("content-type", "").lower().startswith("text/plain"):
                    raise PQError("ROBOTS_UNAVAILABLE", "Robots is not attested plain text", 503)
                text = await read_page(helper.page, "text", 65536)
                parser = RobotFileParser(robots_url)
                parser.parse(text.splitlines())
                allowed = parser.can_fetch("PageQuay", url)
                if not allowed:
                    raise PQError(
                        "ROBOTS_DENIED",
                        "Robots disallows this URL",
                        403,
                        details={**evidence, "allowed": False},
                    )
                return {
                    **evidence,
                    "allowed": True,
                    "basis": "robots_rules",
                    "body_sha256": hashlib.sha256(text.encode()).hexdigest(),
                }
        finally:
            await helper.page.close()

    async def human_guard(self, project, tab, job, *, deadline=None):
        # Passive polling only: no solver, clicks, reload or new navigation budget.
        if deadline is None:
            deadline = time.monotonic() + self.db.policy(project).navigation_timeout_seconds
        while state := await challenge_state(tab.page, evidence=tab.evidence):
            if job:
                job.check_authorization()
            if state == "automatic" and time.monotonic() < deadline:
                await asyncio.sleep(min(0.25, max(0, deadline - time.monotonic())))
                continue
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
            await job.wait_for_human(tab.id, capture, navigation=tab.evidence.snapshot())

    @staticmethod
    def check_scope(tab, expected_url):
        if expected_url is not None and tab.page.url != expected_url:
            raise scope_error(tab.page.url, navigation=tab.evidence.snapshot())

    async def navigate(self, project, request, job, tab_id=None):
        network = self.network_factory(self.db.policy(project))
        if (
            not request.allow_redirects
            and request.expected_url is not None
            and request.url != request.expected_url
        ):
            raise exact_error(request.url)
        strict = request.expected_url is not None or not request.allow_redirects
        if strict:
            require_https(request.url)
        await network.resolve(request.url)
        if tab_id:
            tab = self.tab(project, tab_id)
        else:
            tab = await self.new_tab(project, tab_id=job.tab_id, owner_key_id=job.key_id)
        job.set_tab(tab.id)
        try:
            async with tab.lock, tab.audit.operation("navigate", job, url=request.url):
                state = self.states[project["id"]]
                state.blocked_navigations.discard(tab.page)
                blocked_before = state.proxy.blocked_count
                tab.expected_url = None
                if not request.allow_redirects:
                    tab.expected_url = request.expected_url or request.url
                tab.https_only = strict
                tab.scope_url = request.expected_url
                tab.respect_robots = request.respect_robots
                tab.robots_url = None
                tab.network_denials.clear()
                tab.network_denials_truncated = False
                tab.robots = {"status": "not_checked"}
                if request.respect_robots:
                    tab.robots = await self.check_robots(project, request.url, job)
                    tab.robots_url = request.url
                await self._ensure_guard(project, tab)
                tab.guard_errors.clear()
                errors = tab.guard_errors
                try:
                    deadline = time.monotonic() + self.db.policy(project).navigation_timeout_seconds
                    response = await tab.page.goto(
                        request.url,
                        wait_until=request.wait_until,
                        timeout=self.db.policy(project).navigation_timeout_seconds * 1000,
                    )
                    if errors:
                        raise errors[0]
                    await self.human_guard(project, tab, job, deadline=deadline)
                    if errors:
                        raise errors[0]
                    self.check_scope(tab, request.expected_url)
                    self._upstream_limit(response)
                    if request.respect_robots and tab.page.url != tab.robots_url:
                        tab.robots = await self.check_robots(project, tab.page.url, job)
                        tab.robots_url = tab.page.url
                    checkpoint = tab.evidence.checkpoint(request.expected_url)
                    title = await read_title(tab.page)
                    tab.evidence.verify(checkpoint, request.expected_url)
                    self.events.emit(project, "tab.navigated", tab_id=tab.id)
                    return {
                        "tab_id": tab.id,
                        "url": short_url(tab.page.url),
                        **title,
                        "navigation": tab.evidence.snapshot(),
                        "robots": tab.robots,
                        "network_policy": self.network_attestation(tab),
                    }
                except (PlaywrightTimeout, PlaywrightError) as exc:
                    if errors:
                        raise errors[0] from exc
                    if isinstance(exc, PlaywrightTimeout):
                        raise PQError("TIMEOUT", "Navigation timed out", 504) from exc
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
        finally:
            if getattr(job, "kind", None) == "navigate":
                partial = dict(job.partial_result or {})
                partial.update(
                    tab_id=tab.id,
                    navigation=tab.evidence.snapshot(),
                    robots=tab.robots,
                    network_policy=self.network_attestation(tab),
                )
                job.partial_result = partial

    @staticmethod
    def network_attestation(tab):
        return {
            "schemes": ["https"] if tab.https_only else ["http", "https"],
            "ports": [443] if tab.https_only else [80, 443],
            "url_credentials": "denied",
            "dns": "all_addresses_public",
            "connect": "validated_literal_ip",
            "private_ipv4_ipv6": "denied",
            "service_workers": "blocked",
            "websockets": "blocked",
            "subframe_network": "denied" if tab.https_only else "legacy_public_proxy",
            "refusals": list(tab.network_denials),
            "refusals_truncated": tab.network_denials_truncated,
            "limitations": [
                "DNS checked at routes, page-target redirects and new proxy connections; "
                "existing tunnels remain IP-pinned.",
                "OOPIF redirects are not attested; "
                "strict mode denies all subframe network requests.",
                "Ports reflect production policy; tests may inject local endpoints.",
            ],
        }

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
        async with (
            tab.lock,
            tab.audit.operation("submit_search_form", job, label="next page", url=form["url"]),
        ):
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
        async with tab.lock, tab.audit.operation("actions", job):
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
                async with tab.audit.operation(action.type, job):
                    if action.type == "click":
                        classification = await click_classification(locator)
                        if classification & 1:
                            raise PQError(
                                "FORBIDDEN", "Human verification cannot be automated", 403
                            )
                        if classification & 2:
                            tab.audit.current["label"] = "next page"
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
            return {"tab_id": tab_id, "url": short_url(tab.page.url)}

    async def extract(self, project, tab_id, format, job, *, include_dom=False, expected_url=None):
        tab = self.tab(project, tab_id)
        job.set_tab(tab_id)
        async with tab.lock, tab.audit.operation("extract", job, label=format):
            expected_url = expected_url if expected_url is not None else tab.scope_url
            deadline = time.monotonic() + self.db.policy(project).navigation_timeout_seconds
            while True:
                await self.human_guard(project, tab, job, deadline=deadline)
                self.check_scope(tab, expected_url)
                checkpoint = tab.evidence.checkpoint(expected_url)
                if tab.respect_robots and tab.page.url != tab.robots_url:
                    tab.robots = await self.check_robots(project, tab.page.url, job)
                    tab.robots_url = tab.page.url
                    tab.evidence.verify(checkpoint, expected_url)
                try:
                    artifact_id = uid()
                    if format == "structured":
                        snapshot = await extract_structured(
                            tab.page,
                            include_dom=include_dom,
                            max_bytes=self.settings.max_content_bytes,
                            check=lambda checkpoint=checkpoint: (
                                job.check_authorization(),
                                tab.evidence.verify(checkpoint, expected_url),
                            ),
                            correlation={
                                "request_id": job.request_id,
                                "job_id": job.id,
                                "tab_id": tab_id,
                                "artifact_id": artifact_id,
                            },
                        )
                        if tab.network_denials:
                            snapshot["partial"] = True
                        snapshot.update(
                            navigation=tab.evidence.snapshot(),
                            robots=tab.robots,
                            network_policy=self.network_attestation(tab),
                            captured_at=utc_now(),
                            artifact_id=artifact_id,
                        )
                        data, media = (
                            json.dumps(snapshot, ensure_ascii=False, allow_nan=False),
                            "application/json",
                        )
                    else:
                        value = await read_page(tab.page, format, self.settings.max_content_bytes)
                        if format in {"html", "text"}:
                            data, media = value, "text/html" if format == "html" else "text/plain"
                        else:
                            data, media = json.dumps(value), "application/json"
                except PQError as exc:
                    if exc.code in {
                        "NAVIGATION_CHANGED",
                        "scope_changed",
                    } and await challenge_detected(tab.page, evidence=tab.evidence):
                        continue
                    raise
                if await challenge_detected(tab.page, evidence=tab.evidence):
                    # Discard the unpublished snapshot. Resume captures a fresh document.
                    continue
                self.check_scope(tab, expected_url)
                tab.evidence.verify(checkpoint, expected_url)
                if tab.guard_errors:
                    raise tab.guard_errors[0]
                return {
                    **self.artifacts.put(project, data.encode(), media, artifact_id=artifact_id),
                    "navigation": tab.evidence.snapshot(),
                }

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
        async with tab.lock, tab.audit.operation("screenshot", job):
            return self.artifacts.put(
                project, await self._screenshot(project, tab.page), "image/png", "screenshot:read"
            )

    async def shutdown(self):
        for state in list(self.states.values()):
            await self.stop(state.project, force=True)
        if self.playwright:
            await self.playwright.stop()
        if self.guard_tasks:
            await asyncio.gather(*self.guard_tasks)
        if self.audit_tasks:
            await asyncio.gather(*self.audit_tasks)
