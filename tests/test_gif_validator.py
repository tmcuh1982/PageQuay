import asyncio
import io
from functools import lru_cache

import pytest
from PIL import GifImagePlugin, Image
from pydantic import ValidationError

from pagequay.errors import PQError
from pagequay.gif_validator import check_structure, verify_gif
from pagequay.image_stream import metadata
from pagequay.image_validator import validate_image
from pagequay.models import DownloadImage


@lru_cache(maxsize=8)
def gif(animated=False):
    output = io.BytesIO()
    first = Image.new("P", (32, 24), 0)
    first.putpalette([0, 0, 0, 255, 0, 0] + [0] * 762)
    second = first.copy()
    second.paste(1, (0, 0, 32, 24))
    first.save(
        output,
        format="GIF",
        save_all=animated,
        append_images=[second] if animated else [],
        duration=100,
    )
    return output.getvalue()


@lru_cache(maxsize=4)
def sized_gif(size):
    """A decodable image plus a legal comment extension, never arbitrary trailing bytes."""
    base = gif().replace(b"GIF87a", b"GIF89a", 1)
    remaining = size - len(base) - 3
    blocks = bytearray(b"\x21\xfe")
    while remaining:
        count = min(255, remaining - 1)
        if remaining - count - 1 == 1:
            count -= 1
        assert count > 0
        blocks.append(count)
        blocks.extend(b"x" * count)
        remaining -= count + 1
    blocks.append(0)
    result = base[:-1] + blocks + b";"
    assert len(result) == size
    return result


@lru_cache(maxsize=2)
def sized_png(size):
    import struct
    import zlib

    output = io.BytesIO()
    Image.new("RGB", (32, 24), "blue").save(output, format="PNG")
    base = output.getvalue()
    payload = b"x" * (size - len(base) - 12)
    chunk = b"npAD" + payload  # Legal private ancillary chunk with its actual CRC.
    return (
        base[:-12]
        + struct.pack(">I", len(payload))
        + chunk
        + struct.pack(">I", zlib.crc32(chunk))
        + base[-12:]
    )


@pytest.mark.parametrize("animated", [False, True])
def test_complete_gif_decodes_only_first_image(monkeypatch, animated):
    data = gif(animated)
    assert check_structure(data) == (2 if animated else 1)
    seek = GifImagePlugin.GifImageFile._seek

    def first_only(self, frame, *args, **kwargs):
        assert frame == 0
        return seek(self, frame, *args, **kwargs)

    monkeypatch.setattr(GifImagePlugin.GifImageFile, "_seek", first_only)
    monkeypatch.setattr(
        GifImagePlugin.GifImageFile,
        "n_frames",
        property(lambda self: pytest.fail("must not count frames through Pillow")),
    )
    verify_gif(data)


def test_every_truncation_including_after_first_frame_is_refused():
    data = gif(True)
    for end in range(len(data)):
        with pytest.raises(PQError):
            verify_gif(data[:end])
    with pytest.raises(PQError):
        verify_gif(data + b";")
    # A trailer does not repair a truncated image payload.
    with pytest.raises(PQError):
        verify_gif(data[:-4] + b";")


@pytest.mark.parametrize("size", [5_000_000, 5_000_001, 20_000_000])
async def test_valid_exact_byte_boundaries(size):
    data = sized_gif(size)
    assert check_structure(data) == 1
    await validate_image(data, "image/gif")


async def test_decoder_rejects_over_absolute_limit():
    with pytest.raises(PQError) as caught:
        await validate_image(sized_gif(20_000_001), "image/gif")
    assert caught.value.code == "IMAGE_TOO_LARGE"


def test_gif_dimensions_before_any_decode(monkeypatch):
    monkeypatch.setattr(Image, "open", lambda *a, **k: pytest.fail("decoded before bounds"))
    for width, height, cause in [
        (8193, 1, "gif_axis_limit"),
        (4001, 4000, "gif_pixel_limit"),
        (0, 1, "gif_axis_limit"),
    ]:
        data = bytearray(gif())
        data[6:10] = width.to_bytes(2, "little") + height.to_bytes(2, "little")
        with pytest.raises(PQError) as caught:
            verify_gif(data)
        assert caught.value.details["cause"] == cause


def repeated_frames(count):
    data = gif()
    start = 13 + 3 * (2 << (data[10] & 7))
    return data[:start] + data[start:-1] * count + b";"


def test_frame_budget_and_malformed_first_lzw():
    assert check_structure(repeated_frames(1000)) == 1000
    with pytest.raises(PQError) as caught:
        check_structure(repeated_frames(1001))
    assert caught.value.details["cause"] == "gif_frame_limit"
    data = bytearray(gif())
    start = 13 + 3 * (2 << (data[10] & 7))
    # The first block is GCE when duration is present; locate the image after it.
    descriptor = data.index(0x2C, start)
    payload = descriptor + 11
    size = data[payload - 1]
    data[payload : payload + size] = b"\xff" * size
    with pytest.raises(PQError):
        verify_gif(data)


@pytest.mark.parametrize("value", [True, "20000000", 20_000_000.0, 0, 20_000_001])
def test_strict_byte_budget(value):
    with pytest.raises(ValidationError):
        DownloadImage(
            url="https://example.org/x", expected_url="https://example.org/x", max_bytes=value
        )


@pytest.mark.parametrize("value", [[], None, ["image/gif", "image/gif"], ["image/svg+xml"]])
def test_closed_format_list(value):
    with pytest.raises(ValidationError):
        DownloadImage(
            url="https://example.org/x",
            expected_url="https://example.org/x",
            allowed_media_types=value,
        )


def test_legacy_defaults_and_opt_in_headers():
    request = DownloadImage(url="https://example.org/x", expected_url="https://example.org/x")
    assert request.max_bytes == 5_000_000
    assert request.allowed_media_types == ["image/jpeg", "image/png", "image/webp"]
    for mime in request.allowed_media_types:
        assert metadata(request, request.url, 200, {"content-type": mime}) == (mime, None)
    with pytest.raises(PQError) as caught:
        metadata(request, request.url, 200, {"content-type": "image/gif"})
    assert caught.value.code == "IMAGE_FORMAT_FORBIDDEN"
    request = request.model_copy(
        update={"max_bytes": 20_000_000, "allowed_media_types": ["image/gif"]}
    )
    for length in [None, "20000000", "1"]:
        headers = {"content-type": "image/gif"}
        if length is not None:
            headers["content-length"] = length
        assert metadata(request, request.url, 200, headers)[0] == "image/gif"
    with pytest.raises(PQError):
        metadata(
            request,
            request.url,
            200,
            {"content-type": "image/gif", "content-range": "bytes 0-1/20"},
        )


async def test_decoder_wall_timeout_kills_child(monkeypatch):
    import sys

    import pagequay.image_validator as module

    spawn = asyncio.create_subprocess_exec
    children = []

    async def slow(*args, **kwargs):
        child = await spawn(sys.executable, "-c", "import time; time.sleep(30)", **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(module, "VALIDATION_SECONDS", 0.1)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", slow)
    with pytest.raises(PQError) as caught:
        await validate_image(gif(), "image/gif")
    assert caught.value.code == "IMAGE_TIMEOUT"
    assert caught.value.details["stage"] == "validation"
    assert children[0].returncode is not None


def test_gif87a_and_transparent_interlaced_gif89a():
    output = io.BytesIO()
    image = Image.new("P", (64, 64), 0)
    image.save(output, format="GIF")
    assert output.getvalue().startswith(b"GIF87a")
    verify_gif(output.getvalue())
    output = io.BytesIO()
    image.save(output, format="GIF", transparency=0, interlace=True)
    assert output.getvalue().startswith(b"GIF89a")
    verify_gif(output.getvalue())


async def test_worker_preserves_known_structure_causes():
    for data, code, cause in [
        (gif() + b";", "IMAGE_INVALID", "gif_invalid_termination"),
        (gif(True)[:-1], "IMAGE_INCOMPLETE", "gif_truncated_block"),
    ]:
        with pytest.raises(PQError) as caught:
            await validate_image(data, "image/gif")
        assert caught.value.code == code
        assert caught.value.details["cause"] == cause
        assert caught.value.details["stage"] == "validation"
