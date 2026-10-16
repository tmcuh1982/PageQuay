"""Bounded original-image acquisition on the existing Chromium egress path."""

import asyncio
import base64
import hashlib
import io
import warnings
from contextlib import suppress

from PIL import Image
from playwright.async_api import Error as PlaywrightError

from . import __version__
from .errors import PQError
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
        handle = None
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
            if status != 200:
                raise PQError(
                    "IMAGE_HTTP_STATUS",
                    "Image requires a complete HTTP 200 response",
                    502,
                    details={"cause": "http_status", "http_status": status},
                )
            if mime not in MIMES.values():
                raise PQError(
                    "IMAGE_FORMAT_FORBIDDEN",
                    "Only JPEG, PNG and WebP are supported",
                    415,
                    details={"cause": "unsupported_mime"},
                )
            if headers.get("content-encoding", "identity").lower() != "identity":
                raise PQError(
                    "IMAGE_ENCODING_UNSUPPORTED",
                    "Encoded representation refused",
                    422,
                    details={"cause": "content_encoding"},
                )
            length = headers.get("content-length")
            try:
                length = int(length) if length is not None else None
                if length is not None and length < 0:
                    raise ValueError
            except ValueError as exc:
                raise PQError("IMAGE_INCOMPLETE", "Invalid Content-Length", 422) from exc
            if length is not None and length > self.request.max_bytes:
                raise PQError("IMAGE_TOO_LARGE", "Image exceeds max_bytes", 413)
            handle = (
                await session.send(
                    "Fetch.takeResponseBodyAsStream", {"requestId": event["requestId"]}
                )
            )["stream"]
            data = bytearray()
            while True:
                self.authorize()
                block = await session.send(
                    "IO.read",
                    {"handle": handle, "size": min(65536, self.request.max_bytes - len(data) + 1)},
                )
                # CDP's internal binary framing is decoded here; never exposed in API or logs.
                chunk = (
                    base64.b64decode(block["data"], validate=True)
                    if block.get("base64Encoded")
                    else block["data"].encode()
                )
                if len(data) + len(chunk) > self.request.max_bytes:
                    raise PQError("IMAGE_TOO_LARGE", "Image exceeds max_bytes while reading", 413)
                data.extend(chunk)
                if block.get("eof"):
                    break
            if length is not None and length != len(data):
                raise PQError("IMAGE_INCOMPLETE", "Content-Length differs from received bytes", 422)
            self.verify_scope()
            await asyncio.to_thread(verify_image, bytes(data), mime)
            self.authorize()
            self.verify_scope()
            self.future.set_result((bytes(data), mime, status))
        except Exception as exc:
            if not self.future.done():
                self.future.set_exception(exc)
        finally:
            if handle:
                with suppress(PlaywrightError):
                    await session.send("IO.close", {"handle": handle})
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
            data, mime, status = await collector.future
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
            stage=collector.stage if collector and stage == "navigation" else stage,
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
            observed_at=utc_now(),
            version=__version__,
            command={
                "method": "POST",
                "path": f"/v1/projects/{project['slug']}/download_image",
                "body": request.model_dump(),
            },
            expected="complete original binary image; exact approved final URL",
            observed=code,
            partial_artifact=False,
        )
        raise PQError(
            code,
            exc.message if isinstance(exc, PQError) else "Image acquisition failed",
            exc.status if isinstance(exc, PQError) else 504,
            details=details,
        ) from exc
    finally:
        if navigation:
            navigation.cancel()
            await asyncio.gather(navigation, return_exceptions=True)
        if collector:
            if collector.future.done() and not collector.future.cancelled():
                collector.future.exception()  # Retrieve errors even when navigation failed first.
            else:
                collector.future.cancel()
        if tab:
            # Closing first aborts pending IO.read. Disabling Fetch with a live body stream
            # can leave Chromium waiting indefinitely for its owner to release the response.
            guard, tab.egress_guard = tab.egress_guard, None
            try:
                async with asyncio.timeout(5):
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
                    "Image tab cleanup deadline exceeded",
                    504,
                    details={"stage": "cleanup", "cause": "cleanup_deadline", "retryable": False},
                ) from exc
        job.cleanup_verified = True
