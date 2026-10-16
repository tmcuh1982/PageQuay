"""Disposable decoder receiving bytes only, with no source fetch or artifact writes."""

import asyncio
import os
import resource
import sys

from .errors import PQError

MAX_BYTES = 5_000_000


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
        await process.communicate(data)
        if process.returncode:
            raise PQError(
                "IMAGE_INVALID",
                "Image validation failed in the bounded decoder",
                422,
                details={
                    "cause": "invalid_image_or_decoder_resource_limit",
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
        return 1
    try:
        verify_image(data, sys.argv[1])
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
