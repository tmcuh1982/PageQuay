"""Fixed reads in a clean Chromium realm; never fall back to page-owned JavaScript."""

import asyncio
import json
from contextlib import suppress
from pathlib import Path

from playwright.async_api import Error as PlaywrightError

from .errors import PQError

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


async def isolated_read(page, function, arguments, *, max_bytes, frame=None):
    session = None
    try:
        async with asyncio.timeout(10):
            expected = []
            current = frame or page.main_frame
            while current.parent_frame is not None:
                parent = current.parent_frame
                expected.append(parent.child_frames.index(current))
                current = parent
                if len(expected) > 32:
                    raise PQError("UNAVAILABLE", "Frame nesting exceeds read limit", 503)
            expected.reverse()
            # An OOPIF owns a target; in-process frames use the page target instead.
            if frame is not None and frame != page.main_frame:
                try:
                    session = await page.context.new_cdp_session(frame)
                except PlaywrightError:
                    pass
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
            await session.send("Runtime.enable")
            world = None
            # Never fetch TargetInfo or FrameTree: these copy page-controlled titles,
            # URLs and every frame name before any document budget could be enforced.
            for frame_id in frame_ids:
                candidate = await session.send(
                    "Page.createIsolatedWorld",
                    {"frameId": frame_id, "worldName": "pagequay-read"},
                )
                probe = await session.send(
                    "Runtime.callFunctionOn",
                    {
                        "functionDeclaration": FRAME_PATH,
                        "executionContextId": candidate["executionContextId"],
                        "returnByValue": True,
                    },
                )
                if probe.get("result", {}).get("value") == expected:
                    world = candidate
                    break
            if world is None:
                raise PQError("UNAVAILABLE", "Frame unavailable during extraction", 503)
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
                raise PQError("UNAVAILABLE", "Document extraction failed", 503)
            value = result["result"].get("value")
            if not isinstance(value, str) or len(value) > max_bytes:
                raise PQError("INVALID_INPUT", "Content exceeds configured size limit", 413)
            if len(value.encode("utf-8")) > max_bytes:
                raise PQError("INVALID_INPUT", "Content exceeds configured size limit", 413)
            payload = json.loads(value)
            if payload.get("too_large"):
                raise PQError("INVALID_INPUT", "Content exceeds configured size limit", 413)
            return payload["value"]
    except (PlaywrightError, TimeoutError, KeyError, IndexError, ValueError) as exc:
        raise PQError("UNAVAILABLE", "Document unavailable during extraction", 503) from exc
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
