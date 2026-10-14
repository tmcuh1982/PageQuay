"""Bounded consent detection using Playwright's locators, including open shadows and frames."""

import asyncio
import re

from playwright.async_api import Error as PlaywrightError

from .errors import PQError
from .page_reader import click_classification

# Require a consent container AND cookie-related text AND an exact choice label.
# A standalone "Refuser" button elsewhere on a page is never a candidate.
BANNERS = (
    '[role="dialog"],dialog,[role="alertdialog"],'
    '[id*="cookie" i],[class*="cookie" i],'
    '[id*="consent" i],[class*="consent" i],[aria-label*="cookie" i],'
    "#onetrust-banner-sdk,#didomi-host,#usercentrics-root,#qc-cmp2-container"
)
COOKIE_TEXT = re.compile(r"cookies?|consentement|consent|datenschutz|pliki? cookie", re.I)
CHOICES = {
    "reject": re.compile(
        r"^\s*(?:refuser(?: tout| tous| tous les cookies)?|tout refuser|"
        r"continuer sans accepter|reject(?: all| all cookies)?|decline(?: all)?|"
        r"deny(?: all)?|only necessary(?: cookies)?|necessary cookies only|"
        r"essential cookies only|alle ablehnen|ablehnen|nur notwendige cookies|"
        r"odrzuć(?: wszystkie)?|tylko niezbędne)\s*$",
        re.I,
    ),
    "accept": re.compile(
        r"^\s*(?:accepter(?: tout| tous| tous les cookies)?|tout accepter|"
        r"accept(?: all| all cookies)?|allow all(?: cookies)?|"
        r"alle akzeptieren|akzeptieren|zaakceptuj(?: wszystkie)?)\s*$",
        re.I,
    ),
}
MAX_FRAMES = 8
MAX_BUTTONS = 32


async def visible_frame(frame, main):
    while frame is not main:
        handle = await frame.frame_element()
        try:
            if not await handle.is_visible():
                return False
        finally:
            await handle.dispose()
        frame = frame.parent_frame
        if frame is None:
            return False
    return True


async def validate_cookies(
    page, *, choice="reject", timeout_ms=5000, selector=None, check=lambda: None
):
    """Report a dispatched click, never infer that the site persisted consent."""
    result = {"choice": choice, "status": "not_found"}
    if choice not in CHOICES:
        raise PQError("INVALID_INPUT", "Unknown cookie choice")
    candidates = []
    scan_complete = False
    try:
        async with asyncio.timeout(timeout_ms / 1000):
            while True:
                check()
                scan_complete = False
                frames = list(page.frames)
                # Do not act on an incomplete scan that might hide another matching button.
                if len(frames) > MAX_FRAMES:
                    return {**result, "status": "scan_limit"}
                candidates = []
                banner_found = False
                for frame in frames:
                    if frame.is_detached() or not await visible_frame(frame, page.main_frame):
                        continue
                    banners = frame.locator(selector or BANNERS).filter(has_text=COOKIE_TEXT)
                    count = await banners.count()
                    if count > MAX_BUTTONS:
                        return {**result, "status": "scan_limit"}
                    for index in range(count):
                        if await banners.nth(index).is_visible():
                            banner_found = True
                    buttons = banners.get_by_role("button", name=CHOICES[choice])
                    count = await buttons.count()
                    if count > MAX_BUTTONS:
                        return {**result, "status": "scan_limit"}
                    for index in range(count):
                        button = buttons.nth(index)
                        if await button.is_visible():
                            candidates.append(button)
                if len(candidates) > 1:
                    return {**result, "status": "ambiguous"}
                if candidates:
                    check()
                    button = candidates[0]
                    if await click_classification(button) & 1:
                        raise PQError("FORBIDDEN", "Human verification cannot be automated", 403)
                    await button.click(timeout=timeout_ms)
                    return {**result, "status": "clicked"}
                result["status"] = "choice_unavailable" if banner_found else "not_found"
                scan_complete = True
                await asyncio.sleep(0.1)
    except TimeoutError:
        return result if scan_complete else {**result, "status": "timeout"}
    except PlaywrightError:
        return {**result, "status": "unavailable"}
