"""Main-document evidence and pre-follow redirect interception (no response bodies)."""

import asyncio
import hashlib
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit

from playwright.async_api import Error as PlaywrightError

from .errors import PQError
from .storage import uid


def utc_now():
    return datetime.now(UTC).isoformat()


def safe_target(url):
    parts = urlsplit(url)
    # Preserve an exact digest without exposing query, fragment or credentials.
    host = parts.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    try:
        if parts.port:
            host += f":{parts.port}"
    except ValueError:
        pass
    return {
        "target_url": urlunsplit((parts.scheme, host, parts.path, "", ""))[:2048],
        "target_sha256": hashlib.sha256(url.encode()).hexdigest(),
    }


def exact_error(url, code="URL_MISMATCH"):
    return PQError(code, "Exact URL contract rejected a destination", 409, details=safe_target(url))


def scope_error(url, *, navigation):
    return PQError(
        "scope_changed",
        "Final destination requires explicit scope review",
        409,
        details={**safe_target(url), "navigation": navigation},
    )


def require_https(url):
    try:
        parts = urlsplit(url)
        valid = parts.scheme == "https" and (parts.port or 443) == 443
    except ValueError:
        valid = False
    if not valid:
        raise PQError(
            "NAVIGATION_BLOCKED",
            "HTTPS on port 443 required",
            403,
            details={"cause": "https_required"},
        )


class NavigationEvidence:
    def __init__(self, page):
        self.page = page
        self.navigation_id = uid()
        self.requested_url = page.url
        self.response_url = None
        self.http_status = None
        self.content_type = None
        self.redirect_chain = []
        self.redirect_chain_truncated = False
        self.observed_at = utc_now()
        self.frame_revision = 0
        self.pending_response = None
        self.cf_challenge = False
        page.on("request", self.request)
        page.on("response", self.response)
        page.on("framenavigated", self.navigated)
        page.on("framedetached", self.changed)
        page.on("frameattached", self.changed)

    def changed(self, _):
        self.frame_revision += 1

    def main_request(self, request):
        return request.is_navigation_request() and request.frame == self.page.main_frame

    def request(self, request):
        if not self.main_request(request):
            return
        if request.redirected_from is None:
            self.requested_url = request.url
            self.redirect_chain = []
            self.redirect_chain_truncated = False
        self.response_url = None
        self.http_status = None
        self.content_type = None
        self.pending_response = None
        # Keep the committed challenge signal until a replacement response commits.
        # A request start does not replace the currently displayed document.
        # Invalidate captures at navigation START, including a same-URL reload.
        self.changed(None)

    def response(self, response):
        if not self.main_request(response.request):
            return
        headers = response.headers
        if 300 <= response.status < 400 and headers.get("location"):
            if len(self.redirect_chain) < 20:
                self.redirect_chain.append(
                    {
                        "url": response.url[:4096],
                        "http_status": response.status,
                        "target_url": urljoin(response.url, headers["location"])[:4096],
                    }
                )
            else:
                self.redirect_chain_truncated = True
        else:
            self.pending_response = (
                response.url,
                response.status,
                headers.get("content-type"),
                headers.get("cf-mitigated") == "challenge",
            )

    def navigated(self, frame):
        self.changed(frame)
        if frame != self.page.main_frame:
            return
        self.navigation_id = uid()
        self.observed_at = utc_now()
        self.response_url = self.http_status = self.content_type = None
        # A same-document hash/history commit must not erase a challenge response.
        if (
            self.pending_response
            and urldefrag(self.pending_response[0])[0] == urldefrag(frame.url)[0]
        ):
            self.response_url, self.http_status, self.content_type, self.cf_challenge = (
                self.pending_response
            )
        self.pending_response = None

    def snapshot(self):
        known = (
            self.response_url is not None
            and urldefrag(self.response_url)[0] == urldefrag(self.page.url)[0]
        )
        return {
            "requested_url": self.requested_url[:4096],
            "final_url": self.page.url[:4096],
            "http_status": self.http_status if known else None,
            "http_status_reason": None if known else "no_main_document_response_observed",
            "content_type": self.content_type[:256] if known and self.content_type else None,
            "redirect_chain": list(self.redirect_chain),
            "redirect_chain_truncated": self.redirect_chain_truncated,
            "observed_at": self.observed_at,
            "navigation_id": self.navigation_id,
            "source": "browser_main_document_response",
        }

    def checkpoint(self, expected_url=None):
        if expected_url is not None and self.page.url != expected_url:
            raise scope_error(self.page.url, navigation=self.snapshot())
        return self.navigation_id, self.frame_revision, self.page.main_frame, self.page.url

    def verify(self, checkpoint, expected_url=None):
        if self.checkpoint(expected_url) != checkpoint:
            raise PQError("NAVIGATION_CHANGED", "Document or frame changed during capture", 409)


@asynccontextmanager
async def redirect_guard(
    page, network, *, expected_url=None, allow_redirects=True, https_only=False, contract=None
):
    """Pause HTTP redirects at response headers; never fetch/serialize the body."""
    session = await page.context.new_cdp_session(page)
    tasks = set()
    errors = []
    overloaded = False

    async def paused(event):
        try:
            allowed_url = contract.expected_url if contract is not None else expected_url
            redirects_allowed = (
                (contract.expected_url is None) if contract is not None else allow_redirects
            )
            secure_only = contract.https_only if contract is not None else https_only
            headers = {h["name"].lower(): h["value"] for h in event.get("responseHeaders", [])}
            url = event["request"]["url"]
            target = urljoin(url, headers["location"]) if headers.get("location") else None
            handler = getattr(contract, "response_handler", None)
            # The image collector records redirect headers but never consumes redirect bodies.
            # Policy validation still runs before any redirect is followed.
            if handler is not None and await handler(session, event):
                return
            if target and 300 <= event.get("responseStatusCode", 0) < 400:
                if (
                    event.get("resourceType") == "Document"
                    and not redirects_allowed
                    and urldefrag(url)[0] == urldefrag(allowed_url or url)[0]
                ):
                    if target != (allowed_url or url):
                        raise exact_error(target, "REDIRECT_BLOCKED")
                if secure_only:
                    require_https(target)
                await network.resolve(target)
            await session.send("Fetch.continueRequest", {"requestId": event["requestId"]})
        except PQError as exc:
            if len(errors) < 1:
                errors.append(exc)
            with suppress(PlaywrightError):
                await session.send(
                    "Fetch.failRequest",
                    {
                        "requestId": event["requestId"],
                        "errorReason": "BlockedByClient",
                    },
                )
        except PlaywrightError:
            pass

    def dispatch(event):
        nonlocal overloaded
        if overloaded:
            return
        if len(tasks) >= 64:
            overloaded = True
            if not errors:
                errors.append(
                    PQError(
                        "NAVIGATION_BLOCKED",
                        "Redirect guard capacity exceeded",
                        503,
                        details={"cause": "redirect_guard_capacity"},
                    )
                )
            # Fail closed: do not disable interception and release pending traffic.
            task = asyncio.create_task(page.close())
        else:
            task = asyncio.create_task(paused(event))
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    session.on("Fetch.requestPaused", dispatch)
    try:
        await session.send(
            "Fetch.enable", {"patterns": [{"urlPattern": "*", "requestStage": "Response"}]}
        )
        yield errors
    finally:
        with suppress(PlaywrightError):
            await session.send("Fetch.disable")
        for task in list(tasks):
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        with suppress(PlaywrightError):
            await session.detach()
