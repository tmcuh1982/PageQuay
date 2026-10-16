> Local release 1.1.1 dated 16 October 2026, not published or installed. The previous
> 1.1.0 release still used internal binary CDP Base64. The following acquisition
> guarantees require this correction. The client checks the OpenAPI operation marker
> `x-pagequay-image-transport=chromium-byob-integers-v1` before submitting an image
> POST; version 1.1.0 alone is insufficient.

# Original image acquisition — PageQuay 1.1.1

[Français](DOWNLOAD_IMAGE.md) | [English](DOWNLOAD_IMAGE.en.md)

Minimum package/module/OpenAPI version for the new transport: **1.1.1**. Versions 0.2.2/1.0.1 do not provide this operation. `pq` remains the service launcher; the command is REST `POST /v1/projects/{slug}/download_image`. Existing artifact downloads and screenshots are separate operations.

## Contract

Requires Bearer authentication, an active project, `content:read` and `browser:interact`, checked at admission and throughout the job. The example reads its key from a private file; never place keys in commands, tickets, captures or logs. Artifact GET rechecks authentication, project and content:read.

```json
{
  "url": "https://owebsite-cdn.ubtrobot.com/resources/image/2024/10/13/600674404126789.jpg",
  "expected_url": "https://owebsite-cdn.ubtrobot.com/resources/image/2024/10/13/600674404126789.jpg",
  "allow_redirects": true,
  "max_bytes": 5000000,
  "timeout": 120
}
```

`expected_url` is mandatory and compared exactly against Chromium's main response URL before reading image bytes. With allow_redirects=true, HTTP redirects and technical navigation may be followed, without transferring business approval. A mismatch produces scope_changed with requested/expected/final URLs and cause. False retains the browser's prior redirect refusal. HTTPS/443 only; project/DNS/SSRF policy and validated-IP proxy remain active. No separate HTTP client fetches the source.

`max_bytes`: 1–5000000 bytes, default 5 decimal MB. `timeout`: positive total seconds, default 120, maximum 180, also capped by job_timeout_seconds. It includes queue, startup, navigation, automatic challenge, human waiting, acquisition and validation. Decoder termination has at most one additional second, followed by up to five seconds for tab/guard cleanup. Existing job/tab/browser/connection/storage limits remain.

HTTP 202 returns job_id, reserved tab_id and polling URL. Use:

- GET /v1/projects/{slug}/jobs/{job_id} for state/result/error.
- POST .../jobs/{job_id}/cancel; then wait for terminal state and error.details.cleanup_verified.
- POST .../jobs/{job_id}/resume after manual intervention, restricted to the original key.

Recognized automatic Cloudflare checks can finish within the configured navigation budget and total deadline. Explicit CAPTCHA or unresolved checks enter waiting_for_human with tab/navigation diagnostics and no screenshot for this operation. No solver or CAPTCHA click. Human wait expiry is HUMAN_REQUIRED_TIMEOUT. Manual navigation to an image does not authorize reading it before explicit job resume. The owned tab closes when the job ends.

## Acquisition and integrity

After allowed HTML verification finishes, the main-frame image response is checked at headers and aborted without reading its body. A request-stage interception then supplies an empty document at the exact expected URL, without an upstream request or an encoded body. Its CSP denies resources and permits connections only to its own origin. The isolated JavaScript world receives no additional privileges.

Chromium performs a second GET through the existing routes and proxy. Its final URL, status, MIME, encoding and size are checked again before body consumption. The artifact contains this second response's original bytes; it is not a guaranteed snapshot of the first response. A fresh challenge returned during this fetch is rejected as HTML.

A BYOB reader returns blocks of at most 64 KiB as bounded integer arrays, with one sentinel byte beyond the budget. No acquisition Base64, including internal binary CDP IO, Blob, Data URL, screenshot or direct source HTTP client is used. accept_downloads=False and ordinary browser download cancellation remain.

Requires complete HTTP 200. Partial responses, HTML, forbidden formats and content encodings are rejected. Pillow verifies and decodes solely for validation, without reencoding or stripping metadata; maximum 25 million pixels and no animation. Validation runs in a disposable child with five CPU seconds; cancellation kills it and checks exit within one second. On macOS memory bounds rely on input size, block size and pixel count: no OS RSS ceiling for the decoder or browser is claimed. RLIMIT_AS/DATA attempts were rejected on this host; system settings were not changed. Reading reaches EOF; JPEG/PNG endings and WebP RIFF length are checked. No partial image artifact is published.

Result fields: artifact_id, authenticated download url, verified media_type, size, sha256, expires_at, requested_url, final_url, redirect_chain, http_status, request_id, job_id, tab_id, frame_id, network_request_id and original_bytes=true. Artifact GET returns the original binary attachment. Private, project-isolated 0600 files respect storage quota and the shorter content TTL/artifact retention. Expired artifacts are immediately inaccessible and later purged. An artifact created before terminal job validation is removed on failure. Cancellation closes stream and tab.

## Errors and reproduction

Job errors include code, details.stage, known cause or unknown, retryable, available correlation, version, timezone-aware ISO timestamp, exact REST command/body, expected/observed outcome and absence of partial artifact. Stages distinguish admission, queue, startup, navigation, human verification, final scope, acquisition, artifact creation and cleanup. GET errors use artifact_download; unknown/unauthorized source URLs remain unknown. Keep the original job result to reproduce the source. JSON/authentication errors never grant access to another project's data.

Specific codes: scope_changed, IMAGE_HTTP_STATUS, IMAGE_FORMAT_FORBIDDEN, IMAGE_ENCODING_UNSUPPORTED, IMAGE_TOO_LARGE, IMAGE_INCOMPLETE, IMAGE_INVALID, IMAGE_HTML_RESPONSE, IMAGE_TIMEOUT, HUMAN_REQUIRED_TIMEOUT, IMAGE_CANCELLED, IMAGE_CLEANUP_FAILED. Existing startup/navigation/network codes remain. IMAGE_ACQUISITION_FAILED means an unknown cause, not an invented site/network attribution. Cleanup failures carry cleanup_verified=false, the resource identifier and the preceding error when available. Failed physical removal must not leave an unpublished artifact downloadable. Invalid JSON bodies are not echoed; retain the client request for exact reproduction.

Do not automatically replay a POST whose response was lost: this operation does not yet offer idempotency. Use retained IDs. Shared reports need an exact public URL without secrets, version, actual method/path/body, expected/observed, timezone-aware time and available IDs. Never copy Authorization, cookies or secret-bearing signed URLs. Historical direct HTTPS reader failures are not PageQuay failures and have no retroactive PageQuay jobs.

## UBTECH recipe on an installed service

Requires installed/restarted PageQuay >=1.1.1 with dependencies, authorized service/project, GUI session for headed mode and existing Bearer in a 0600 file containing only the token. The client requires httpx and Pillow. Adapt service/project/private paths:

```sh
.venv/bin/python examples/download_image.py \
  'https://owebsite-cdn.ubtrobot.com/resources/image/2024/10/13/600674404126789.jpg' \
  --expected-url 'https://owebsite-cdn.ubtrobot.com/resources/image/2024/10/13/600674404126789.jpg' \
  --service 'http://127.0.0.1:8766' --project universrobot \
  --bearer-file /private/path/pagequay-token --timeout 120 \
  --allow-redirects --output /private/path/walker-s1-original.jpg
```

The client calls only PageQuay, displays job IDs, waits, streams the artifact to a private temporary file, verifies size/hash/signature and renames it. Failures leave no partial output. Human waiting is explicit (exit 2), without diagnostic screenshots for image acquisition. Run the client with the same arguments and --job-id ID to follow that job; add --resume for an explicit resume request. Neither mode submits a new acquisition POST. A lost admission response without an ID remains uncertain and is never automatically replayed. Artifact transfer checks a 30-second deadline between blocks, plus at most the 15-second HTTP read timeout before noticing a stall. Expected outcome: complete original or reproducible typed error.

## UniversRobot scope

No UniversRobot file was modified in this change; the Walker S1 preview was not tested. Future integration must call this PageQuay operation only, preserve asynchronous/private caching and recheck authorization at every step, without direct HTTPS fallback. Local ImageMagick creates previews. Existing rules: keep original, WebP quality 80, longest side <=1200 px, thumbnail <=400 px without upscaling, flag images below 600 px. Preview grants neither approval nor publication; no pause/schedule changed.

Fixture tests and disposable live-network validation are separated in [the report](testing/DOWNLOAD_IMAGE_REPORT.en.md). They do not prove installed deployment or authenticated UniversRobot service validation.
