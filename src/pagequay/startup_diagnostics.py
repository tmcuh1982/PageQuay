"""Diagnostics bornés de lancement ; aucun chemin, log Chromium ou secret exporté."""

import re

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeout

STEPS = {
    "proxy_start",
    "playwright_start",
    "selector_registration",
    "browser_launch",
    "browser_setup",
}


def startup_error_details(error, step):
    step = step if step in STEPS else "unknown"
    cause = "UNKNOWN_STARTUP_FAILURE"
    error_class = (
        "PLAYWRIGHT_TIMEOUT"
        if isinstance(error, PlaywrightTimeout)
        else "PLAYWRIGHT_ERROR"
        if isinstance(error, PlaywrightError)
        else "OTHER"
    )
    if step == "browser_launch":
        message = str(error)
        if isinstance(error, PlaywrightTimeout):
            cause = "BROWSER_LAUNCH_TIMEOUT"
        elif isinstance(error, PlaywrightError) and message.startswith(
            "BrowserType.launch_persistent_context:"
        ):
            if re.match(
                r"^BrowserType\.launch_persistent_context: (?:Executable doesn't exist at |"
                r"Failed to launch chromium because executable doesn't exist at )",
                message,
            ):
                cause = "BROWSER_EXECUTABLE_MISSING"
            elif "PAGEQUAY_BROWSER_EXECUTABLE_MISSING" in message:
                cause = "BROWSER_EXECUTABLE_MISSING"
            elif re.search(r"SingletonLock: File exists(?:\s|$)", message):
                cause = "BROWSER_PROFILE_LOCK_EXISTS"
    return {"stage": "startup", "startup_step": step, "cause": cause, "error_class": error_class}
