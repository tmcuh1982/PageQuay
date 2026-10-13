"""Bounded diagnostic facts; page-controlled exception text is never published/logged."""

import json
import logging
import time

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeout

from . import __version__
from .errors import PQError
from .navigation import utc_now

logger = logging.getLogger("pagequay.extraction")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())


def cause_code(exc, detached=False):
    if detached:
        return "FRAME_DETACHED"
    if isinstance(exc, (TimeoutError, PlaywrightTimeout)):
        return "TIMEOUT"
    if isinstance(exc, (KeyError, ValueError, IndexError)):
        return "SCHEMA_REJECTED"
    if isinstance(exc, PQError):
        return (exc.details or {}).get(
            "cause", "SIZE_LIMIT" if exc.status == 413 else "OTHER_ERROR"
        )
    if isinstance(exc, PlaywrightError):
        message = str(exc)[:2048].lower()
        if "frame owner inventory limit" in message or "frame shadow inventory limit" in message:
            return "SIZE_LIMIT"
        if any(
            marker in message
            for marker in (
                "cannot find context",
                "execution context was destroyed",
                "no frame for given id",
                "cannot find default execution context",
                "cannot find frame",
            )
        ):
            return "WORLD_NOT_FOUND"
        if "frame was detached" in message or "frame has been detached" in message:
            return "FRAME_DETACHED"
    return "OTHER_ERROR"


class ReadTrace:
    def __init__(self, frame, correlation=None):
        self.frame = frame
        self.correlation = correlation or {}
        self.stage = "visibility"
        self.started = time.perf_counter()
        self.limit_ms = 10000
        self.selection = None

    def detached(self):
        return self.frame.is_detached()

    def success(self):
        if self.correlation:
            logger.info(
                "frame_read_success %s",
                json.dumps(
                    {
                        **self.correlation,
                        "reader_version": __version__,
                        "observed_at": utc_now(),
                        "stage": self.stage,
                        "duration_ms": round((time.perf_counter() - self.started) * 1000, 3),
                        "limit_ms": self.limit_ms,
                        "is_detached": self.detached(),
                        "context_selection": self.selection,
                    },
                    separators=(",", ":"),
                ),
            )

    def failure(self, exc):
        diagnostic = {
            "cause": cause_code(exc, self.detached()),
            "stage": self.stage,
            "duration_ms": round((time.perf_counter() - self.started) * 1000, 3),
            "limit_ms": self.limit_ms,
            "is_detached": self.detached(),
            "observed_at": utc_now(),
            "interpretation": "observed_state_and_exception_indicator",
        }
        if self.selection is not None:
            diagnostic["context_selection"] = self.selection
        chain, current = [], exc
        while current is not None and len(chain) < 8:
            # Retain original exception classes and typed causes, excluding arbitrary
            # message/stack source lines that may contain Bearer/cookies/page/query data.
            chain.append({"type": type(current).__name__, "cause": cause_code(current)})
            current = current.__cause__
        logger.warning(
            "frame_read_failure %s",
            json.dumps(
                {
                    **self.correlation,
                    "reader_version": __version__,
                    **diagnostic,
                    "exception_chain": chain,
                    "exception_text": "redacted_untrusted_exception_text",
                },
                separators=(",", ":"),
            ),
        )
        return diagnostic
