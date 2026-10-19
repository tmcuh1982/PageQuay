"""Disposable decoder receiving bytes only, with no source fetch or artifact writes."""

import asyncio
import os
import resource
import sys

from .errors import PQError

MAX_BYTES = 20_000_000
VALIDATION_SECONDS = 10

# Fixed exit codes avoid exposing decoder/provider messages or unbounded output.
FAILURES = {
    10: ("IMAGE_INCOMPLETE", "gif_truncated_block"),
    11: ("IMAGE_INVALID", "gif_axis_limit"),
    12: ("IMAGE_INVALID", "gif_pixel_limit"),
    13: ("IMAGE_INVALID", "gif_frame_limit"),
    14: ("IMAGE_INVALID", "gif_first_image_decode"),
    15: ("IMAGE_INVALID", "gif_invalid_structure"),
    16: ("IMAGE_TOO_LARGE", "decoder_input_limit"),
    17: ("IMAGE_INVALID", "gif_signature"),
    18: ("IMAGE_INVALID", "gif_background_index"),
    19: ("IMAGE_INVALID", "gif_invalid_termination"),
    20: ("IMAGE_INVALID", "gif_control_block"),
    21: ("IMAGE_INVALID", "gif_extension_header"),
    22: ("IMAGE_INVALID", "gif_plain_text_header"),
    23: ("IMAGE_INVALID", "gif_plain_text_bounds"),
    24: ("IMAGE_INVALID", "gif_palette_index"),
    25: ("IMAGE_INVALID", "gif_unknown_block"),
    26: ("IMAGE_INVALID", "gif_frame_bounds"),
    27: ("IMAGE_INVALID", "gif_lzw_code_size"),
    28: ("IMAGE_INVALID", "gif_empty_image_data"),
}


async def validate_image(data, mime):
    """Cancellation kills the decoder instead of leaving a background thread running."""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "pagequay.image_validator",
        mime,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
        env={key: value for key, value in os.environ.items() if key in {"PATH", "PYTHONPATH"}},
    )
    try:
        try:
            async with asyncio.timeout(VALIDATION_SECONDS):
                await process.communicate(data)
        except TimeoutError as exc:
            raise PQError(
                "IMAGE_TIMEOUT",
                "Image validation deadline exceeded",
                504,
                details={"stage": "validation", "cause": "decoder_wall_deadline"},
            ) from exc
        if process.returncode:
            code, cause = FAILURES.get(
                process.returncode,
                ("IMAGE_INVALID", "invalid_image_or_decoder_resource_limit"),
            )
            raise PQError(
                code,
                "Image validation failed in the bounded decoder",
                422,
                details={
                    "stage": "validation",
                    "cause": cause,
                    "decoder_exit_code": process.returncode,
                },
            )
    finally:
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            try:
                async with asyncio.timeout(1):
                    await process.wait()
            except (TimeoutError, asyncio.CancelledError) as exc:
                raise PQError(
                    "IMAGE_CLEANUP_FAILED",
                    "Decoder termination could not be confirmed",
                    503,
                    details={
                        "stage": "cleanup",
                        "cause": "decoder_exit_unconfirmed",
                        "cleanup_verified": False,
                    },
                ) from exc


def main():
    # Limits apply only to this disposable child, never the service or browser.
    if sys.platform != "darwin":
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
    from .image_download import verify_image

    data = sys.stdin.buffer.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        return 16
    try:
        verify_image(data, sys.argv[1])
    except PQError as exc:
        cause = (exc.details or {}).get("cause", "")
        for exit_code, (code, known_cause) in FAILURES.items():
            if code == exc.code and known_cause == cause:
                return exit_code
        return 15 if sys.argv[1] == "image/gif" else 1
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
