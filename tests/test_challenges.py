from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from pagequay.browser import challenge_detected


@pytest.mark.parametrize(
    ("url", "text", "expected"),
    [
        ("https://www.google.com/sorry/index?continue=search", "", True),
        (
            "https://www.google.com/search?q=test",
            "Nos systèmes ont détecté un trafic exceptionnel sur votre réseau informatique.",
            True,
        ),
        ("https://www.google.com/search?q=test", "Résultats de recherche", False),
        ("https://example.org/sorry/index", "Article ordinaire", False),
    ],
)
async def test_google_challenge_localization_and_url(url, text, expected):
    body = SimpleNamespace(inner_text=AsyncMock(return_value=text))
    frames = SimpleNamespace(count=AsyncMock(return_value=0))
    page = SimpleNamespace(
        url=url,
        title=AsyncMock(return_value="Page"),
        locator=lambda selector: body if selector == "body" else frames,
    )
    assert bool(await challenge_detected(page)) is expected
