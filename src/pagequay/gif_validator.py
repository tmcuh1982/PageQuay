"""Bounded GIF structure walk and first-image decode, never animation coalescing.

Layout reference: https://www.w3.org/Graphics/GIF/spec-gif89a.txt
Later images' compressed pixels are deliberately not decoded.
"""

import io
import warnings

from PIL import Image

from .errors import PQError

MAX_AXIS = 8192
MAX_PIXELS = 16_000_000
MAX_FRAMES = 1000


def invalid(cause, *, incomplete=False):
    raise PQError(
        "IMAGE_INCOMPLETE" if incomplete else "IMAGE_INVALID",
        "GIF validation failed in the bounded decoder",
        422,
        details={"stage": "validation", "cause": cause},
    )


def dimensions(width, height):
    if not 0 < width <= MAX_AXIS or not 0 < height <= MAX_AXIS:
        invalid("gif_axis_limit")
    if width * height > MAX_PIXELS:
        invalid("gif_pixel_limit")


def check_structure(data):
    """Skip payloads by offset; never copy/concatenate extension or animation data."""
    offset = 0

    def take(size):
        nonlocal offset
        end = offset + size
        if end > len(data):
            invalid("gif_truncated_block", incomplete=True)
        result = memoryview(data)[offset:end]
        offset = end
        return result

    def byte():
        return take(1)[0]

    def subblocks():
        count = 0
        while size := byte():
            take(size)
            count += size
        return count

    if bytes(take(6)) not in {b"GIF87a", b"GIF89a"}:
        invalid("gif_signature")
    screen = take(7)
    width, height = int.from_bytes(screen[:2], "little"), int.from_bytes(screen[2:4], "little")
    dimensions(width, height)
    global_colors = (2 << (screen[4] & 7)) if screen[4] & 128 else 0
    if global_colors:
        take(3 * global_colors)
        if screen[5] >= global_colors:
            invalid("gif_background_index")
    frames = 0
    control_pending = False
    transparency = None
    while True:
        marker = byte()
        if marker == 0x3B:
            if not frames or control_pending or offset != len(data):
                invalid("gif_invalid_termination")
            return frames
        if marker == 0x21:
            label = byte()
            if label == 0xF9:
                if control_pending or byte() != 4:
                    invalid("gif_control_block")
                control = take(4)
                if control[0] & 0xE0 or ((control[0] >> 2) & 7) > 3 or byte() != 0:
                    invalid("gif_control_block")
                transparency = control[3] if control[0] & 1 else None
                control_pending = True
            elif label in {0xFF, 0x01}:
                size = 11 if label == 0xFF else 12
                if byte() != size:
                    invalid("gif_extension_header")
                header = take(size)
                if label == 0x01:
                    if not global_colors or not header[8] or not header[9]:
                        invalid("gif_plain_text_header")
                    left, top, tw, th = (
                        int.from_bytes(header[i : i + 2], "little") for i in (0, 2, 4, 6)
                    )
                    if not tw or not th or left + tw > width or top + th > height:
                        invalid("gif_plain_text_bounds")
                    if max(header[10], header[11], transparency or 0) >= global_colors:
                        invalid("gif_palette_index")
                    control_pending, transparency = False, None
                subblocks()
            else:
                # Comments and future extension labels use length-prefixed sub-blocks.
                subblocks()
            continue
        if marker != 0x2C:
            invalid("gif_unknown_block")
        frames += 1
        if frames > MAX_FRAMES:
            invalid("gif_frame_limit")
        descriptor = take(9)
        left, top, fw, fh = (int.from_bytes(descriptor[i : i + 2], "little") for i in (0, 2, 4, 6))
        # Apply the same bounds to later descriptors too, without decoding them.
        dimensions(fw, fh)
        if left + fw > width or top + fh > height or descriptor[8] & 0x18:
            invalid("gif_frame_bounds")
        colors = global_colors
        if descriptor[8] & 128:
            colors = 2 << (descriptor[8] & 7)
            take(3 * colors)
        if not colors or (transparency is not None and transparency >= colors):
            invalid("gif_palette_index")
        if not 2 <= byte() <= 8:
            invalid("gif_lzw_code_size")
        if not subblocks():
            invalid("gif_empty_image_data")
        control_pending, transparency = False, None


def verify_gif(data):
    check_structure(data)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data), formats=["GIF"]) as image:
                dimensions(*image.size)
                # open() selects the first image; n_frames/seek/iteration are forbidden here.
                image.load()
    except PQError:
        raise
    except Exception as exc:
        raise PQError(
            "IMAGE_INVALID",
            "GIF first image validation failed in the bounded decoder",
            422,
            details={"stage": "validation", "cause": "gif_first_image_decode"},
        ) from exc
