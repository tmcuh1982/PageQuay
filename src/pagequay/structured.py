"""Bounded extraction of the live DOM, including open shadows and child frames."""

import asyncio
import hashlib
import time
from pathlib import Path
from urllib.parse import urlsplit

from playwright.async_api import Error as PlaywrightError

from . import __version__
from .diagnostics import ReadTrace, logger
from .errors import PQError
from .page_reader import isolated_read

SCRIPT = Path(__file__).with_name("extraction.js").read_text()
SCRIPT_SHA256 = hashlib.sha256(SCRIPT.encode("utf-8")).hexdigest()
logger.info(
    "structured_reader_loaded version=%s schema_version=1.0 script_sha256=%s",
    __version__,
    SCRIPT_SHA256,
)
MAX_FRAMES = 8  # Visible reads, including the main document; shared 40s deadline.
MAX_FRAME_INVENTORY = 32  # Hidden frames are reported without consuming a read slot.
logger.info(
    "structured_reader_budget max_frames=%s max_frame_inventory=%s", MAX_FRAMES, MAX_FRAME_INVENTORY
)


async def extract_structured(
    page, *, include_dom=False, max_bytes=2_000_000, check=lambda: None, correlation=None
):
    frames = [page.main_frame, *(frame for frame in page.frames if frame != page.main_frame)]
    frame_ids = {frame: f"f{index}" for index, frame in enumerate(frames)}
    documents = []
    frame_limit_reached = len(frames) > MAX_FRAME_INVENTORY
    truncated = frame_limit_reached
    read_frames = 0
    deadline = time.monotonic() + 40
    for frame in frames[:MAX_FRAME_INVENTORY]:
        if time.monotonic() >= deadline:
            raise PQError("TIMEOUT", "Structured extraction budget exhausted", 504)
        check()
        entry = {
            "frame_id": frame_ids[frame],
            "parent_frame_id": frame_ids.get(frame.parent_frame),
            "name": frame.name[:256],
            "url": frame.url[:4096],
        }
        trace = ReadTrace(frame, {**(correlation or {}), "frame_id": entry["frame_id"]})
        try:
            async with asyncio.timeout(min(10, max(0, deadline - time.monotonic()))):
                if frame != page.main_frame:
                    handle = await frame.frame_element()
                    try:
                        # Align child-frame reads with extraction.js DOM exclusions.
                        if (
                            not await handle.is_visible()
                            or await handle.get_attribute("aria-hidden") == "true"
                        ):
                            entry.update(status="omitted", reason="hidden_frame")
                            documents.append(entry)
                            continue
                    finally:
                        await handle.dispose()
                if urlsplit(frame.url).scheme not in {"http", "https", "about"}:
                    if frame == page.main_frame:
                        raise PQError("NAVIGATION_BLOCKED", "Unsupported document scheme", 403)
                    entry.update(status="unavailable", reason="unsupported_frame_scheme")
                    documents.append(entry)
                    continue
                if read_frames >= MAX_FRAMES:
                    frame_limit_reached = truncated = True
                    break
                read_frames += 1
                document = await asyncio.wait_for(
                    isolated_read(
                        page,
                        "function(options) { const value = (" + SCRIPT + ")(options); "
                        "const output = JSON.stringify({value}); "
                        "if (output.length > options.max_bytes || "
                        "new TextEncoder().encode(output).length > options.max_bytes) "
                        "return JSON.stringify({too_large: true}); return output; }",
                        {
                            "include_dom": include_dom,
                            "text_budget": min(160000, max_bytes // 8),
                            "max_bytes": max_bytes,
                        },
                        frame=frame,
                        max_bytes=max_bytes,
                        trace=trace,
                    ),
                    10,
                )
                if (
                    not isinstance(document, dict)
                    or not isinstance(document.get("truncated"), bool)
                    or not isinstance(document.get("blocks"), list)
                ):
                    trace.stage = "serialization"
                    raise PQError(
                        "UNAVAILABLE",
                        "Structured schema rejected",
                        503,
                        details={"cause": "SCHEMA_REJECTED"},
                    )
                entry.update(
                    status="extracted", document=document, context_selection=trace.selection
                )
                truncated |= document["truncated"]
                if frame != page.main_frame:
                    trace.success()
        except (PlaywrightError, TimeoutError, PQError) as exc:
            if frame == page.main_frame:
                raise
            details = (
                exc.details
                if isinstance(exc, PQError) and (exc.details or {}).get("stage")
                else None
            ) or trace.failure(exc)
            entry.update(
                status="unavailable",
                reason="frame_detached_or_unresponsive",
                cause_code=details["cause"],
                diagnostic=details,
            )
        documents.append(entry)
    primary = documents[0]["document"]
    return {
        "schema_version": "1.0",
        **primary,
        "source": "rendered_dom",
        "frame_id": documents[0]["frame_id"],
        "frames": documents[1:],
        "truncated": truncated,
        "partial": truncated or any(entry["status"] == "unavailable" for entry in documents),
        "frame_limit_reached": frame_limit_reached,
        "limitations": [
            "Only mounted DOM content is captured; no automatic scrolling or clicks.",
            "Closed shadow DOM is not traversed; known browser frames may be captured separately.",
            "Canvas and visual SVG content require a screenshot for visual interpretation.",
            "Node IDs refer to this snapshot only; they are not action selectors.",
        ],
    }
