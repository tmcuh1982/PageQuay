from types import SimpleNamespace

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
async def test_google_challenge_localization_and_url(url, text, expected, monkeypatch):
    async def bounded_read(*args, **kwargs):
        return {"title": "Page", "text": text, "frame": False}

    monkeypatch.setattr("pagequay.browser.read_page", bounded_read)
    page = SimpleNamespace(url=url)
    assert bool(await challenge_detected(page)) is expected
