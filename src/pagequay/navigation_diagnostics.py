"""Codes de navigation générés par Chromium ; aucune exception brute exportée."""

import math
import re

CAUSES = {
    "ERR_CERT_DATE_INVALID": "TLS_CERTIFICATE_DATE_INVALID",
    "ERR_CERT_AUTHORITY_INVALID": "TLS_CERTIFICATE_AUTHORITY_INVALID",
    "ERR_CERT_COMMON_NAME_INVALID": "TLS_CERTIFICATE_NAME_INVALID",
    "ERR_SSL_PROTOCOL_ERROR": "TLS_PROTOCOL_ERROR",
    "ERR_NAME_NOT_RESOLVED": "DNS_NAME_NOT_RESOLVED",
    "ERR_CONNECTION_REFUSED": "CONNECTION_REFUSED",
    "ERR_CONNECTION_RESET": "CONNECTION_RESET",
    "ERR_EMPTY_RESPONSE": "EMPTY_RESPONSE",
}


def navigation_error_details(message: str) -> dict | None:
    # Un message JS/title ou une mention dans le call log n'est pas une erreur goto.
    match = re.match(r"^Page\.goto: net::(ERR_[A-Z_]+)(?:\s|$)", message)
    if not match or match.group(1) not in CAUSES:
        return None
    code = match.group(1)
    return {"cause": CAUSES[code], "stage": "navigation", "browser_error": code}


NAVIGATION_STEPS = frozenset(
    {
        "goto",
        "human_guard",
        "scope_check",
        "robots_redirect",
        "cookie_consent",
        "title",
        "result",
    }
)


def navigation_timeout_details(step, budget_seconds, elapsed_seconds, *, source):
    """Métadonnées locales fermées, sans lire le texte de l’exception ou une URL."""
    causes = {"playwright": "PLAYWRIGHT_TIMEOUT", "pagequay": "PAGEQUAY_TIMEOUT"}
    if (
        type(step) is not str
        or step not in NAVIGATION_STEPS
        or type(source) is not str
        or source not in causes
        or type(budget_seconds) is not int
        or not 1 <= budget_seconds <= 120
        or type(elapsed_seconds) not in (int, float)
        or not 0 <= elapsed_seconds <= 86400
        or not math.isfinite(elapsed_seconds)
    ):
        return None
    return {
        "stage": "navigation",
        "cause": causes[source],
        "navigation_step": step,
        "budget_ms": budget_seconds * 1000,
        "elapsed_ms": int(elapsed_seconds * 1000),
    }
