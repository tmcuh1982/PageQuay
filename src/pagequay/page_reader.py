"""Fixed reads in a clean Chromium realm; never fall back to page-owned JavaScript."""

import asyncio
import json
from contextlib import suppress
from pathlib import Path

from playwright.async_api import Error as PlaywrightError

from .diagnostics import ReadTrace
from .errors import PQError
from .frame_context import bounded_path, frame_path

SCRIPT = Path(__file__).with_name("page_reader.js").read_text()
FRAME_PATH = """function() {
  const path = [];
  let current = window;
  while (current !== current.top) {
    if (path.length >= 32) return null;
    const parent = current.parent;
    let index = 0;
    while (index < 128 && parent[index] !== current) index++;
    if (index === 128) return null;
    path.push(index);
    current = parent;
  }
  return path.reverse();
}"""


async def isolated_read(page, function, arguments, *, max_bytes, frame=None, trace=None):
    session = None
    trace = trace or ReadTrace(frame or page.main_frame)
    try:
        async with asyncio.timeout(10):
            trace.stage = "context_selection"
            trace.selection = {
                "session_type": "unattached",
                "candidate_count": 0,
                "expected_path": None,
                "observed_paths": [],
                "paths_truncated": False,
                "failure": None,
                "path_source": "isolated_frame_owners",
            }
            expected = await frame_path(frame or page.main_frame)
            trace.selection["expected_path"] = expected
            trace.selection["session_type"] = "page"
            # Find the target that owns this frame. An in-process descendant of an
            # OOPIF belongs to that ancestor target, not to the top page target.
            trace.stage = "cdp_session"
            owner = frame or page.main_frame
            while owner != page.main_frame:
                try:
                    session = await page.context.new_cdp_session(owner)
                    trace.selection["session_type"] = (
                        "frame_target" if owner == frame else "ancestor_frame_target"
                    )
                    break
                except PlaywrightError as exc:
                    if "does not have a separate CDP session" not in str(exc):
                        raise
                    owner = owner.parent_frame
            if session is None:
                session = await page.context.new_cdp_session(page)
            frame_ids = []

            def context_created(event):
                context = event["context"]
                data = context.get("auxData", {})
                if data.get("isDefault") and len(frame_ids) < 128:
                    frame_id = data.get("frameId")
                    if isinstance(frame_id, str) and len(frame_id) <= 128:
                        frame_ids.append(frame_id)

            session.on("Runtime.executionContextCreated", context_created)
            trace.stage = "context_selection"
            await session.send("Runtime.enable")
            trace.selection["candidate_count"] = len(frame_ids)
            world = None
            # Never fetch TargetInfo or FrameTree: these copy page-controlled titles,
            # URLs and every frame name before any document budget could be enforced.
            for frame_id in frame_ids:
                trace.stage = "isolated_world"
                candidate = await session.send(
                    "Page.createIsolatedWorld",
                    {"frameId": frame_id, "worldName": "pagequay-read"},
                )
                trace.stage = "context_selection"
                probe = await session.send(
                    "Runtime.callFunctionOn",
                    {
                        "functionDeclaration": FRAME_PATH,
                        "executionContextId": candidate["executionContextId"],
                        "returnByValue": True,
                    },
                )
                if "exceptionDetails" in probe:
                    raise PQError(
                        "UNAVAILABLE",
                        "Frame context probe failed",
                        503,
                        details={"cause": "JAVASCRIPT_EXCEPTION"},
                    )
                observed = bounded_path(probe.get("result", {}).get("value"))
                if len(trace.selection["observed_paths"]) < 8:
                    trace.selection["observed_paths"].append(observed)
                else:
                    trace.selection["paths_truncated"] = True
                if observed == expected:
                    world = candidate
                    break
            if world is None:
                trace.selection["failure"] = "no_candidates" if not frame_ids else "path_mismatch"
                raise PQError(
                    "UNAVAILABLE",
                    "Frame unavailable during extraction",
                    503,
                    details={"cause": "WORLD_NOT_FOUND"},
                )
            trace.selection["selected_path"] = expected
            # Inventory and context must still identify the same mounted frame.
            if await frame_path(frame or page.main_frame) != expected:
                raise PQError(
                    "NAVIGATION_CHANGED",
                    "Frame position changed during selection",
                    409,
                    details={"cause": "WORLD_NOT_FOUND"},
                )
            trace.stage = "extraction"
            result = await session.send(
                "Runtime.callFunctionOn",
                {
                    "functionDeclaration": function,
                    "executionContextId": world["executionContextId"],
                    "arguments": [{"value": arguments}],
                    "returnByValue": True,
                    "awaitPromise": True,
                },
            )
            if "exceptionDetails" in result:
                raise PQError(
                    "UNAVAILABLE",
                    "Document extraction failed",
                    503,
                    details={"cause": "JAVASCRIPT_EXCEPTION"},
                )
            trace.stage = "serialization"
            value = result["result"].get("value")
            if not isinstance(value, str) or len(value) > max_bytes:
                raise PQError("INVALID_INPUT", "Content exceeds configured size limit", 413)
            if len(value.encode("utf-8")) > max_bytes:
                raise PQError("INVALID_INPUT", "Content exceeds configured size limit", 413)
            payload = json.loads(value)
            if not isinstance(payload, dict) or (
                "value" not in payload and not payload.get("too_large")
            ):
                raise PQError(
                    "UNAVAILABLE", "Read schema rejected", 503, details={"cause": "SCHEMA_REJECTED"}
                )
            if payload.get("too_large"):
                raise PQError("INVALID_INPUT", "Content exceeds configured size limit", 413)
            # Verify the SAME isolated execution context still exists after capture.
            trace.stage = "context_verification"
            verified = await session.send(
                "Runtime.callFunctionOn",
                {
                    "functionDeclaration": "function() { return true; }",
                    "executionContextId": world["executionContextId"],
                    "returnByValue": True,
                },
            )
            if verified.get("result", {}).get("value") is not True:
                raise PQError(
                    "NAVIGATION_CHANGED",
                    "Read context changed during capture",
                    409,
                    details={"cause": "WORLD_NOT_FOUND"},
                )
            if await frame_path(frame or page.main_frame) != expected:
                raise PQError(
                    "NAVIGATION_CHANGED",
                    "Frame position changed during capture",
                    409,
                    details={"cause": "WORLD_NOT_FOUND"},
                )
            return payload["value"]
    except PQError as exc:
        if not (exc.details or {}).get("stage"):
            exc.details = trace.failure(exc)
        raise
    except (PlaywrightError, TimeoutError, KeyError, IndexError, ValueError) as exc:
        details = trace.failure(exc)
        if isinstance(exc, (KeyError, ValueError, IndexError)):
            details["cause"] = "SCHEMA_REJECTED"
        raise PQError(
            "UNAVAILABLE", "Document unavailable during extraction", 503, details=details
        ) from exc
    finally:
        if session is not None:
            with suppress(PlaywrightError, TimeoutError):
                await asyncio.wait_for(session.detach(), 2)


async def read_page(page, kind, max_bytes=2_000_000, **options):
    return await isolated_read(
        page,
        SCRIPT,
        {"kind": kind, "max_bytes": max_bytes, **options},
        max_bytes=max_bytes * 6 + 128 if kind in {"html", "text"} else max_bytes,
    )


async def read_title(page):
    return await read_page(page, "title", max_bytes=16384)


async def click_classification(locator):
    # Return only a two-bit integer, never page text, preserving Playwright selector support.
    result = await locator.evaluate("""el => {
      try {
      const text = [el.innerText, el.getAttribute('aria-label'),
        el.closest('[data-sitekey],[class*=captcha]')?.innerText]
        .filter(Boolean).join(' ').toLowerCase();
      let mask = 0;
      for (const marker of ['i am not a robot', "i'm not a robot", 'i’m not a robot',
        'je ne suis pas un robot', 'i am human', "i'm human", 'captcha'])
        if (text.includes(marker) === true) mask |= 1;
      const normalized = ' ' + text.trim().replace(/\\s+/g, ' ') + ' ';
      for (const label of ['next','next page','suivant','page suivante','more results'])
        if (normalized === ' ' + label + ' ' || normalized === ' ' + label + ' ' + label + ' ')
          mask |= 2;
      return mask;
      } catch { return -1; }
    }""")
    if type(result) is not int or not 0 <= result <= 3:
        raise PQError("UNAVAILABLE", "Invalid action classification", 503)
    return result
