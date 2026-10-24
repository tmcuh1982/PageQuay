from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from pagequay.errors import PQError
from pagequay.network_diagnostics import diagnostic_url, network_refusal


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/private",
        "http://127.1/private",
        "http://0x7f.0.0.1/private",
        "http://[::1]/",
        "https://internal.local/path",
        "https://localhost/",
        "https://intranet/",
        "file:///private/key",
        "https://example.org/\nSECRET",
        "https://example.org\\secret",
    ],
)
def test_private_or_malformed_url_is_not_logged(url):
    assert diagnostic_url(url)["url"] is None


def test_secrets_removed_and_url_budget_explicit():
    result = diagnostic_url("https://user:password@example.org/asset.js?token=SECRET#PRIVATE")
    assert result == dict(
        url="https://example.org/asset.js", url_redacted=True, url_truncated=False
    )
    result = diagnostic_url("https://example.org/" + "a" * 3000)
    assert len(result["url"]) == 2048 and result["url_truncated"] is True


@pytest.mark.parametrize(
    ("navigation", "main", "expected"),
    [(True, True, True), (False, True, False), (True, False, False), (False, False, False)],
)
def test_main_document_requires_both_navigation_and_main_frame(navigation, main, expected):
    frame = object()
    request = SimpleNamespace(
        url="https://example.org/asset",
        frame=frame if main else object(),
        resource_type="document" if navigation else "script",
        is_navigation_request=Mock(return_value=navigation),
    )
    result = network_refusal(
        request,
        SimpleNamespace(main_frame=frame),
        PQError("NAVIGATION_BLOCKED", "x", 403, details={"cause": "dns_failed"}),
    )
    assert result["main_document"] is expected
    assert result["is_navigation_request"] is navigation
    assert result["frame_role"] == ("main_frame" if main else "child_frame")
