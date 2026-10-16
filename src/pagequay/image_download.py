"""Bounded original-image acquisition on the existing Chromium egress path."""

import asyncio
import hashlib
import io
import warnings
from contextlib import suppress

from PIL import Image
from playwright.async_api import Error as PlaywrightError

from . import __version__
from .errors import PQError
from .image_stream import metadata, read_image
from .image_validator import validate_image
from .models import Navigate
from .navigation import utc_now

MIMES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


def verify_image(data, mime):
    """Decode only for validation; return the untouched representation bytes."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if MIMES.get(image.format) != mime:
                    raise ValueError("signature_mime_mismatch")
                # Bound validation memory, including malicious small compressed files.
                if image.width * image.height > 25_000_000:
                    raise ValueError("pixel_limit")
                image.verify()
            with Image.open(io.BytesIO(data)) as image:
                for index in range(getattr(image, "n_frames", 1)):
                    if index >= 1:
                        raise ValueError("animated_image_not_supported")
                    image.seek(index)
                    image.load()
        if mime == "image/jpeg" and not data.endswith(b"\xff\xd9"):
            raise ValueError("jpeg_end_missing")
        if mime == "image/png" and not data.endswith(b"\x00\x00\x00\x00IEND\xaeB`\x82"):
            raise ValueError("png_end_missing")
        if mime == "image/webp" and (
            data[:4] != b"RIFF" or int.from_bytes(data[4:8], "little") + 8 != len(data)
        ):
            raise ValueError("webp_length_mismatch")
    except Exception as exc:
        raise PQError(
            "IMAGE_INVALID",
            "Image signature or completeness validation failed",
            422,
            details={"cause": "invalid_or_incomplete_image"},
        ) from exc


class ImageResponse:
    def __init__(self, request, job, frame_id, tab):
        self.request, self.job, self.frame_id = request, job, frame_id
        self.tab, self.revision = tab, None
        self.future = asyncio.get_running_loop().create_future()
        self.final_url = None
        self.redirects = []
        self.network_id = None
        self.stage = "navigation"
        self.bootstrap = False
        self.streaming = False
        self.stream_error = None
        self.session = None

    def authorize(self):
        self.job.check_authorization()

    def verify_scope(self):
        if self.revision != self.tab.evidence.frame_revision:
            raise PQError(
                "NAVIGATION_CHANGED",
                "Frame changed during image acquisition",
                409,
                details={"cause": "frame_changed_during_acquisition"},
            )

    async def __call__(self, session, event):
        self.session = session
        if self.bootstrap:
            if (
                event.get("resourceType") == "Document"
                and event.get("frameId") == self.frame_id
                and "responseStatusCode" not in event
                and event["request"]["url"] == self.request.expected_url
            ):
                self.authorize()
                # At REQUEST stage the omitted body means an empty body, not Base64.
                await session.send(
                    "Fetch.fulfillRequest",
                    {
                        "requestId": event["requestId"],
                        "responseCode": 200,
                        "responseHeaders": [
                            {"name": "Content-Type", "value": "text/html; charset=utf-8"},
                            {"name": "Content-Length", "value": "0"},
                            {"name": "Cache-Control", "value": "no-store"},
                            {
                                "name": "Content-Security-Policy",
                                "value": "default-src 'none'; connect-src 'self'",
                            },
                        ],
                    },
                )
                return True
            return False
        if self.streaming:
            if event.get("frameId") != self.frame_id:
                return False
            if event.get("resourceType") == "Document":
                self.stream_error = PQError("NAVIGATION_CHANGED", "Image document changed", 409)
                await session.send(
                    "Fetch.failRequest",
                    {
                        "requestId": event["requestId"],
                        "errorReason": "Aborted",
                    },
                )
                return True
            if event.get("resourceType") != "Fetch":
                return False
            if "responseStatusCode" not in event:
                return False
            url = event["request"]["url"]
            self.final_url = url
            self.network_id = event.get("networkId")
            status = event["responseStatusCode"]
            if 300 <= status < 400:
                # The ordinary redirect guard validates policy before following.
                if not self.request.allow_redirects:
                    self.stream_error = PQError("REDIRECT_BLOCKED", "Image fetch redirected", 409)
                elif len(self.redirects) < 20:
                    from urllib.parse import urljoin

                    headers = {
                        h["name"].lower(): h["value"] for h in event.get("responseHeaders", [])
                    }
                    self.redirects.append(
                        {
                            "url": url,
                            "status": status,
                            "target_url": urljoin(url, headers.get("location", "")),
                            "phase": "acquisition",
                        }
                    )
                    return False
                else:
                    self.stream_error = PQError("IMAGE_REDIRECT_LIMIT", "Too many redirects")
            elif url != self.request.expected_url:
                self.stage = "final_scope"
                self.stream_error = PQError(
                    "scope_changed",
                    "Final image URL changed",
                    409,
                    details={"cause": "exact_final_url_mismatch", "final_url": url},
                )
            if self.stream_error:
                await session.send(
                    "Fetch.failRequest",
                    {
                        "requestId": event["requestId"],
                        "errorReason": "Aborted",
                    },
                )
                return True
            try:
                self.authorize()
                metadata(
                    self.request,
                    url,
                    status,
                    {h["name"].lower(): h["value"] for h in event.get("responseHeaders", [])},
                )
            except PQError as exc:
                self.stream_error = exc
                await session.send(
                    "Fetch.failRequest",
                    {
                        "requestId": event["requestId"],
                        "errorReason": "Aborted",
                    },
                )
                return True
            return False
        if event.get("resourceType") != "Document" or event.get("frameId") != self.frame_id:
            return False
        if self.future.done():
            return True
        if self.revision is not None:
            self.future.set_exception(
                PQError(
                    "NAVIGATION_CHANGED",
                    "A second document interrupted image acquisition",
                    409,
                    details={
                        "cause": "concurrent_main_document_response",
                        "observed_url": event["request"]["url"],
                    },
                )
            )
            return True
        url = event["request"]["url"]
        status = event.get("responseStatusCode", 0)
        headers = {h["name"].lower(): h["value"] for h in event.get("responseHeaders", [])}
        if 300 <= status < 400 and headers.get("location"):
            if len(self.redirects) >= 20:
                self.future.set_exception(PQError("IMAGE_REDIRECT_LIMIT", "Too many redirects"))
                return True  # Remain paused until the owned tab is closed.
            from urllib.parse import urljoin

            self.redirects.append(
                {"url": url, "status": status, "target_url": urljoin(url, headers["location"])}
            )
            return False
        mime = headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if mime in {"text/html", "application/xhtml+xml"}:
            # The normal navigation/challenge guard owns HTML. Never export it as an image.
            return False
        self.final_url = url
        self.revision = self.tab.evidence.frame_revision
        self.network_id = event.get("networkId")
        try:
            self.authorize()
            self.stage = "final_scope"
            if url != self.request.expected_url:
                raise PQError(
                    "scope_changed",
                    "Final image URL requires explicit approval",
                    409,
                    details={"cause": "exact_final_url_mismatch"},
                )
            self.stage = "acquisition"
            mime, _ = metadata(self.request, url, status, headers)
            if self.job.status == "waiting_for_human":
                await self.job.resume.wait()
                self.authorize()
            self.future.set_result((mime, status))
        except Exception as exc:
            if not self.future.done():
                self.future.set_exception(exc)
        finally:
            # Do not transfer binary CDP bodies: that protocol encodes them in Base64.
            with suppress(PlaywrightError):
                await session.send(
                    "Fetch.failRequest", {"requestId": event["requestId"], "errorReason": "Aborted"}
                )
        return True


async def download_image(browser, project, request, job):
    tab = collector = navigation = None
    stage = "startup"
    try:
        async with asyncio.timeout(min(request.timeout, browser.settings.job_timeout_seconds)):
            job.check_authorization()
            tab = await browser.new_tab(project, tab_id=job.tab_id, owner_key_id=job.key_id)
            job.set_tab(tab.id)
            session = await tab.page.context.new_cdp_session(tab.page)
            try:
                frame_id = (await session.send("Page.getFrameTree"))["frameTree"]["frame"]["id"]
            finally:
                await session.detach()
            collector = ImageResponse(request, job, frame_id, tab)
            tab.response_handler = collector
            stage = "navigation"
            navigation = asyncio.create_task(
                browser.navigate(
                    project,
                    Navigate(
                        url=request.url,
                        expected_url=request.expected_url,
                        allow_redirects=request.allow_redirects,
                    ),
                    job,
                    tab.id,
                )
            )
            done, _ = await asyncio.wait(
                [navigation, collector.future], return_when=asyncio.FIRST_COMPLETED
            )
            if collector.future not in done:
                # goto may fail after intentional Fetch.failRequest; yield to its collector.
                await asyncio.sleep(0)
                if not collector.future.done():
                    await navigation
                    raise PQError(
                        "IMAGE_HTML_RESPONSE",
                        "Navigation returned HTML, not an image",
                        422,
                        details={"cause": "html_after_challenge_check"},
                    )
            await collector.future
            navigation.cancel()
            await asyncio.gather(navigation, return_exceptions=True)
            navigation = None
            async with (
                tab.lock,
                tab.audit.operation("download_image", job, url=request.expected_url),
            ):
                data, mime, status = await read_image(tab, collector)
                await validate_image(data, mime)
            collector.authorize()
            collector.verify_scope()
            stage = "artifact_creation"
            artifact = browser.artifacts.put(project, data, mime, image=True)
            job.uncommitted_artifact = artifact["artifact_id"]
            return {
                **artifact,
                "sha256": hashlib.sha256(data).hexdigest(),
                "requested_url": request.url,
                "final_url": collector.final_url,
                "redirect_chain": collector.redirects,
                "http_status": status,
                "request_id": job.request_id,
                "job_id": job.id,
                "tab_id": tab.id,
                "frame_id": frame_id,
                "network_request_id": collector.network_id,
                "original_bytes": True,
            }
    except Exception as exc:
        if isinstance(exc, PQError):
            code, cause = exc.code, (exc.details or {}).get("cause", exc.code)
        else:
            code = "IMAGE_TIMEOUT" if isinstance(exc, TimeoutError) else "IMAGE_ACQUISITION_FAILED"
            cause = "total_deadline" if isinstance(exc, TimeoutError) else "unknown"
        if job.status == "waiting_for_human":
            stage = "human_verification"
            if isinstance(exc, TimeoutError):
                code, cause = "HUMAN_REQUIRED_TIMEOUT", "total_deadline_waiting_for_human"
        details = dict(exc.details or {}) if isinstance(exc, PQError) else {}
        details.update(
            stage=details.get("stage")
            or (collector.stage if collector and stage == "navigation" else stage),
            cause=cause,
            retryable=code in {"IMAGE_TIMEOUT", "UPSTREAM_UNAVAILABLE"},
            requested_url=request.url,
            expected_url=request.expected_url,
            final_url=(collector.final_url if collector else None)
            or (tab.page.url if tab else None),
            redirect_chain=collector.redirects if collector else [],
            request_id=job.request_id,
            job_id=job.id,
            tab_id=job.tab_id,
            frame_id=collector.frame_id if collector else None,
            network_request_id=collector.network_id if collector else None,
            observed_at=utc_now(),
            version=__version__,
            command={
                "method": "POST",
                "path": f"/v1/projects/{project['slug']}/download_image",
                "body": request.model_dump(),
            },
            expected="complete original binary image; exact approved final URL",
            observed=code,
            partial_artifact=details.get("partial_artifact", False),
        )
        job.image_failure = {"code": code, "details": details}
        raise PQError(
            code,
            exc.message if isinstance(exc, PQError) else "Image acquisition failed",
            exc.status if isinstance(exc, PQError) else 504,
            details=details,
        ) from exc
    finally:
        try:
            async with asyncio.timeout(5):
                if navigation:
                    navigation.cancel()
                    await asyncio.gather(navigation, return_exceptions=True)
                if collector:
                    if collector.future.done() and not collector.future.cancelled():
                        collector.future.exception()
                    else:
                        collector.future.cancel()
                if tab:
                    # Close before disabling interception to abort pending body reads.
                    guard, tab.egress_guard = tab.egress_guard, None
                    with suppress(PlaywrightError):
                        await tab.page.close()
                    if not tab.page.is_closed():
                        raise PQError(
                            "IMAGE_CLEANUP_FAILED",
                            "Image tab did not close",
                            503,
                            details={
                                "stage": "cleanup",
                                "cause": "tab_still_open",
                                "retryable": False,
                            },
                        )
                    if guard:
                        await guard.__aexit__(None, None, None)
        except TimeoutError as exc:
            raise PQError(
                "IMAGE_CLEANUP_FAILED",
                "Image operation cleanup deadline exceeded",
                504,
                details={"stage": "cleanup", "cause": "cleanup_deadline", "retryable": False},
            ) from exc
        # If startup never returned ownership of a tab, its cleanup is not attested here.
        job.cleanup_verified = tab is not None
