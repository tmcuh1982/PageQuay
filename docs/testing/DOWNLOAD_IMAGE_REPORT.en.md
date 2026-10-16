# download_image validation — October 15, 2026

[Français](DOWNLOAD_IMAGE_REPORT.md) | [English](DOWNLOAD_IMAGE_REPORT.en.md)

Historical working version PageQuay 1.1.0; REST addition, no pq launcher subcommand. Installed service/UniversRobot were not changed.

## Local checks

- Final general suite: **287 passed, 95 skipped**, existing Starlette/httpx deprecation; `.venv/bin/pytest -q --tb=short`.
- Targeted Chromium navigation/challenge/client: **63 passed**; `.venv/bin/pytest tests/test_download_image.py tests/test_download_image_client.py tests/test_acquisition_browser.py tests/test_challenges.py --browser -q --tb=short`. Native WS denial also validated in an earlier 64-test run including test_native_websocket_blocking.py.
- Contract/jobs/acquisition: **42 passed**; `.venv/bin/pytest tests/test_download_image.py tests/test_download_image_client.py tests/test_jobs.py tests/test_openapi.py --browser -q --tb=short`.
- Final acquisition: **27 passed**; `.venv/bin/pytest tests/test_download_image.py --browser -q --tb=short`. Includes concurrent navigation during reading, refusing stale publication; exact error varies with Chromium notification order (navigation changed/interrupted invalid body).
- Ruff on changed/added Python, git diff --check and uv sync --locked --extra dev --offline pass. Package/module 1.1.0; served/committed public OpenAPI equality tested.

These overlapping historical suites are distinct from October 16 release checks: **292 passed/96 skipped general and 72 targeted Chromium passed**, documented in [release notes](../releases/1.1.0.en.md).

Acquisition uses real Chromium and simulated local HTTP server. Local HTTP is test-injected only; production stays HTTPS/443. Cases: identical bytes/hash, unreencoded JPEG/PNG/WebP validation, approved redirects/wrong destination/disabled redirects/private IP, resolved automatic challenge/explicit human waiting/total human deadline, HTML/false MIME/truncation/missing Content-Length/stream size cap/status errors, queue/acquisition deadline, cancellation during human wait/stream, revocation, expiry/purge/project rights, private 0600 client file, truncated/oversized/hash-mismatch/forbidden client download, no partial output, removal of uncommitted artifact and disk-write failure.

Initial sandbox runs failed before acquisition because local sockets were denied; reruns with sockets allowed produced the passing results. Those denials are not PQ/UBTECH failures.

## Separate real-network recipe

Executed **October 15, 2026, 23:32:53 Europe/Warsaw (+02:00)**, 2026-10-15T21:32:53.412660+00:00. Disposable source-1.1.0 service, fresh headless profile, normal production network policy, temporary image-recipe project/ephemeral Bearer never displayed. No installed UniversRobot key used. First 23:28 run also succeeded with same bytes/hash.

Actual shell command: `.venv/bin/python /private/tmp/pq-live-image.py`. The temporary recipe called real HTTP/ASGI API/Bearer validation, polled job and downloaded authenticated artifact. Reproducible installed-service equivalent: [image guide](../DOWNLOAD_IMAGE.en.md).

```http
POST /v1/projects/image-recipe/download_image
```

```json
{"url":"https://owebsite-cdn.ubtrobot.com/resources/image/2024/10/13/600674404126789.jpg","expected_url":"https://owebsite-cdn.ubtrobot.com/resources/image/2024/10/13/600674404126789.jpg","allow_redirects":true,"max_bytes":5000000,"timeout":120}
```

Expected: complete original JPEG, exact final URL, private binary artifact, signature/completeness validation, identical acquired/downloaded size/hash, verified close/purge.

Observed: **completed**, HTTP 200, verified image/jpeg, **689381 bytes**, identical requested/final URL, no redirect, successful JPEG validation. Authenticated GET returned the same size/SHA-256:

```text
f83f4625a8ee91ae51532e26ac5ee9044d0c972834a44815b7022fa32b4af38c
```

| Correlation | Value |
| --- | --- |
| request | f3cb9a327a2f6ce65bc0bc00 |
| job | bee737a7219bc4dc589850a505b2a664 |
| tab | c3b8ad4f8d7e23cf56e2fd51c89b4d81 |
| Chromium frame | 2D0558F7FC37BBA44B2235909BBA32D9 |
| Chromium network request | 7CF7C8A1CF557B43C4979838730FA990 |
| artifact | 15b050bcef75f99af24c19cde891b160 |

Owned tab closed, purge verified and temporary service directory removed. IDs are historical traces, no longer downloadable resources. No real Cloudflare challenge observed; fixture handling does not claim successful real CAPTCHA resolution.

## Installed-service limits

This does not prove installed download_image availability, acquisition using UniversRobot session/project/Bearer or Walker S1 preview. Those need >=1.1.0 deployment and existing private key on the target. This change did not deploy/restart it. Previously inspected 0.2.2 API lacked download_image and had no such recipe job. Historical direct HTTPS timeouts remain separate and are not attributed to PQ. No approval/publication/pause/schedule change was made during that recipe.
