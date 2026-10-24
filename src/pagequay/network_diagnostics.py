"""Diagnostic borné des requêtes refusées, sans paramètres ni identifiants URL."""

import ipaddress
import re
from urllib.parse import urlsplit, urlunsplit

from .errors import PQError

RESOURCE_TYPES = frozenset(
    {
        "document",
        "stylesheet",
        "image",
        "media",
        "font",
        "script",
        "texttrack",
        "xhr",
        "fetch",
        "eventsource",
        "websocket",
        "manifest",
        "other",
    }
)


def diagnostic_url(value):
    """Ne jamais résoudre le nom ni conserver userinfo, query ou fragment."""
    try:
        if (
            not isinstance(value, str)
            or len(value) > 16384
            or any(ord(c) < 33 or ord(c) == 127 for c in value)
            or "\\" in value
        ):
            raise ValueError("URL invalide")
        parsed = urlsplit(value)
        host = (parsed.hostname or "").encode("idna").decode().lower().rstrip(".")
        if parsed.scheme not in {"http", "https"} or not host or "%" in host:
            raise ValueError("URL non HTTP")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if re.fullmatch(r"(?:0x[0-9a-f]+|[0-9]+)(?:\.(?:0x[0-9a-f]+|[0-9]+)){0,3}", host):
                raise ValueError("Adresse numérique non canonique") from None
            if "." not in host or host.endswith(
                (".localhost", ".local", ".internal", ".lan", ".home", ".test")
            ):
                raise ValueError("Hôte local") from None
        else:
            if not address.is_global or address.is_multicast or address.is_reserved:
                raise ValueError("Adresse non publique")
        authority = "[" + host + "]" if ":" in host else host
        if parsed.port is not None:
            authority += ":" + str(parsed.port)
        result = urlunsplit((parsed.scheme, authority, parsed.path, "", ""))
        if len(result) > 2048:
            return dict(url=result[:2048], url_redacted=True, url_truncated=True)
        return dict(url=result, url_redacted=result != value, url_truncated=False)
    except (ValueError, UnicodeError):
        return dict(url=None, url_redacted=True, url_truncated=False)


def _refusal(url, resource, navigation, main_frame, error):
    return {
        "code": error.code,
        "cause": (error.details or {}).get("cause", error.code),
        "main_document": navigation and main_frame,
        "is_navigation_request": navigation,
        "frame_role": "main_frame" if main_frame else "child_frame",
        "resource_type": resource if resource in RESOURCE_TYPES else "other",
        **diagnostic_url(url),
    }


def network_refusal(request, page, error):
    return _refusal(
        request.url,
        request.resource_type,
        request.is_navigation_request(),
        request.frame == page.main_frame,
        error,
    )


async def resolve_navigation(network, url):
    """Le précontrôle est une requête du document principal, même sans onglet/job."""
    try:
        return await network.resolve(url)
    except PQError as error:
        error.details = {
            **(error.details or {}),
            "stage": "navigation",
            "network_refusal": _refusal(url, "document", True, True, error),
        }
        raise
