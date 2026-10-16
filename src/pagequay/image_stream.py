"""Read an original with Chromium fetch and JSON integer blocks, never binary CDP IO."""

import json

from playwright.async_api import Error as PlaywrightError

from .errors import PQError

MIMES = {"image/jpeg", "image/png", "image/webp"}


def metadata(request, url, status, headers):
    if url != request.expected_url:
        raise PQError(
            "scope_changed",
            "Final image URL changed",
            409,
            details={"cause": "exact_final_url_mismatch", "final_url": url},
        )
    if status != 200:
        raise PQError(
            "IMAGE_HTTP_STATUS",
            "Complete HTTP 200 required",
            502,
            details={"cause": "http_status", "http_status": status},
        )
    mime = headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if mime not in MIMES:
        code = (
            "IMAGE_HTML_RESPONSE"
            if mime in {"text/html", "application/xhtml+xml"}
            else "IMAGE_FORMAT_FORBIDDEN"
        )
        raise PQError(
            code, "Response is not a supported image", 415, details={"cause": "unsupported_mime"}
        )
    if headers.get("content-encoding", "identity").lower() != "identity":
        raise PQError(
            "IMAGE_ENCODING_UNSUPPORTED",
            "Encoded representation refused",
            422,
            details={"cause": "content_encoding"},
        )
    try:
        length = int(headers["content-length"]) if "content-length" in headers else None
        if length is not None and length < 0:
            raise ValueError
    except ValueError as exc:
        raise PQError("IMAGE_INCOMPLETE", "Invalid Content-Length", 422) from exc
    if length is not None and length > request.max_bytes:
        raise PQError("IMAGE_TOO_LARGE", "Image exceeds max_bytes", 413)
    return mime, length


async def read_image(tab, collector):
    """Bootstrap an empty same-origin document without sending an upstream request.

    CDP fulfills only a REQUEST-stage event and omits its optional body entirely.
    A fresh GET then runs inside Chromium, with all existing routes/proxy guards.
    The source response is read once through a BYOB reader, never a Blob/Data URL.
    """
    session = collector.session
    collector.bootstrap = True
    collector.stage = "stream_startup"
    await session.send(
        "Fetch.enable",
        {
            "patterns": [
                {"urlPattern": "*", "requestStage": "Response"},
                {"urlPattern": "*", "resourceType": "Document", "requestStage": "Request"},
            ]
        },
    )
    await tab.page.goto(collector.request.expected_url, wait_until="domcontentloaded")
    if tab.page.url != collector.request.expected_url:
        raise PQError("scope_changed", "Bootstrap document URL changed", 409)
    collector.bootstrap = False
    await session.send(
        "Fetch.enable",
        {
            "patterns": [
                {"urlPattern": "*", "requestStage": "Response"},
            ]
        },
    )
    collector.revision = tab.evidence.frame_revision
    collector.verify_scope()
    collector.streaming = True
    collector.stage = "acquisition"
    world = await session.send(
        "Page.createIsolatedWorld",
        {
            "frameId": collector.frame_id,
            "worldName": "pagequay-image-stream",
        },
    )

    async def evaluate(expression):
        collector.authorize()
        collector.verify_scope()
        result = await session.send(
            "Runtime.evaluate",
            {
                "expression": expression,
                "contextId": world["executionContextId"],
                "returnByValue": True,
                "awaitPromise": True,
            },
        )
        if collector.stream_error:
            raise collector.stream_error
        if tab.guard_errors:
            raise tab.guard_errors[0]
        collector.verify_scope()
        if "exceptionDetails" in result:
            raise PQError(
                "IMAGE_INCOMPLETE",
                "Browser image stream failed",
                422,
                details={"cause": "browser_stream_interrupted"},
            )
        return result["result"].get("value")

    try:
        info = await evaluate(
            f"""(async () => {{
            globalThis.pqResponse = await fetch({json.dumps(collector.request.expected_url)},
                {{credentials: 'same-origin', cache: 'no-store'}});
            return {{url: pqResponse.url, status: pqResponse.status,
                    headers: Object.fromEntries(pqResponse.headers)}};
        }})()"""
        )
        mime, length = metadata(collector.request, info["url"], info["status"], info["headers"])
        await evaluate("globalThis.pqReader = pqResponse.body.getReader({mode: 'byob'}); true")
        data = bytearray()
        while True:
            size = min(65536, collector.request.max_bytes - len(data) + 1)
            block = await evaluate(
                f"""(async () => {{
                const {{value, done}} = await pqReader.read(new Uint8Array({size}));
                return {{data: value ? Array.from(value) : [], eof: done}};
            }})()"""
            )
            chunk = block["data"]
            if len(chunk) > size or len(data) + len(chunk) > collector.request.max_bytes:
                raise PQError("IMAGE_TOO_LARGE", "Image exceeds max_bytes while reading", 413)
            data.extend(chunk)
            if block["eof"]:
                break
        if length is not None and length != len(data):
            raise PQError("IMAGE_INCOMPLETE", "Content-Length differs from received bytes", 422)
        collector.authorize()
        collector.verify_scope()
        return bytes(data), mime, info["status"]
    except PlaywrightError as exc:
        if collector.stream_error:
            raise collector.stream_error from exc
        raise
    # The caller closes the owned tab, cancelling the reader on every exit path.
