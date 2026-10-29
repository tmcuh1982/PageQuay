"""AVIF explicite, original intact et décodeur borné existant."""

import io

import pytest
from PIL import Image

from pagequay.errors import PQError
from pagequay.image_download import verify_image
from pagequay.image_validator import validate_image
from pagequay.models import DownloadImage

URL = "https://example.com/image"


def original():
    out = io.BytesIO()
    Image.new("RGB", (32, 24), "blue").save(out, format="AVIF")
    return out.getvalue()


def test_avif_is_opt_in_and_defaults_stay_unchanged():
    request = DownloadImage(url=URL, expected_url=URL, allowed_media_types=["image/avif"])
    assert request.allowed_media_types == ["image/avif"]
    assert "image/avif" not in DownloadImage(url=URL, expected_url=URL).allowed_media_types
    with pytest.raises(ValueError):
        DownloadImage(url=URL, expected_url=URL, allowed_media_types=["image/svg+xml"])


def test_complete_avif_decodes_and_bytes_are_unchanged():
    body = original()
    saved = bytes(body)
    verify_image(body, "image/avif")
    assert body == saved


@pytest.mark.parametrize("change", ["short", "half", "overrun", "html", "sequence", "wrong_mime"])
def test_invalid_avif_refused(change):
    body = original()
    mime = "image/avif"
    if change == "short":
        body = body[:15]
    if change == "half":
        body = body[: len(body) // 2]
    if change == "overrun":
        body = (len(body) + 1).to_bytes(4, "big") + body[4:]
    if change == "html":
        body = b"<html>not an AVIF</html>"
    if change == "sequence":
        body = body.replace(b"avif", b"avis")
    if change == "wrong_mime":
        mime = "image/png"
    with pytest.raises(PQError):
        verify_image(body, mime)


@pytest.mark.asyncio
async def test_avif_passes_bounded_child_decoder():
    await validate_image(original(), "image/avif")
    with pytest.raises(PQError):
        await validate_image(original()[:-8], "image/avif")
