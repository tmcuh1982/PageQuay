"""Bounded extraction of the live DOM, including open shadows and child frames."""

import asyncio
from pathlib import Path
from urllib.parse import urlsplit

from playwright.async_api import Error as PlaywrightError

from .errors import PQError

SCRIPT = Path(__file__).with_name("extraction.js").read_text()
MAX_FRAMES = 4  # Includes the main document.


async def extract_structured(page, *, include_dom=False, max_bytes=2_000_000, check=lambda: None):
    frames = [page.main_frame, *(frame for frame in page.frames if frame != page.main_frame)]
    frame_ids = {frame: f"f{index}" for index, frame in enumerate(frames)}
    documents = []
    truncated = len(frames) > MAX_FRAMES
    for frame in frames[:MAX_FRAMES]:
        check()
        entry = {
            "frame_id": frame_ids[frame],
            "parent_frame_id": frame_ids.get(frame.parent_frame),
            "name": frame.name[:256],
            "url": frame.url[:2048],
        }
        if urlsplit(frame.url).scheme not in {"http", "https", "about"}:
            if frame == page.main_frame:
                raise PQError("NAVIGATION_BLOCKED", "Unsupported document scheme", 403)
            entry.update(status="unavailable", reason="unsupported_frame_scheme")
            documents.append(entry)
            continue
        try:
            if frame != page.main_frame:
                handle = await frame.frame_element()
                try:
                    if not await handle.is_visible():
                        entry.update(status="omitted", reason="hidden_frame")
                        documents.append(entry)
                        continue
                finally:
                    await handle.dispose()
            document = await asyncio.wait_for(
                frame.evaluate(
                    SCRIPT,
                    {"include_dom": include_dom, "text_budget": min(40000, max_bytes // 32)},
                ),
                10,
            )
            entry.update(status="extracted", document=document)
            truncated |= document["truncated"]
        except (PlaywrightError, TimeoutError):
            if frame == page.main_frame:
                raise
            entry.update(status="unavailable", reason="frame_detached_or_unresponsive")
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
        "frame_limit_reached": len(frames) > MAX_FRAMES,
        "limitations": [
            "Only mounted DOM content is captured; no automatic scrolling or clicks.",
            "Closed shadow roots are inaccessible.",
            "Canvas and visual SVG content require a screenshot for visual interpretation.",
            "Node IDs refer to this snapshot only; they are not action selectors.",
        ],
    }
