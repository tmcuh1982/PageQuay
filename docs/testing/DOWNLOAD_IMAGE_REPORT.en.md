# download_image validation — October 15, 2026

[Français](DOWNLOAD_IMAGE_REPORT.md) | [English](DOWNLOAD_IMAGE_REPORT.en.md)

Historical working version PageQuay 1.1.0; REST addition, no pq launcher subcommand. Installed service/UniversRobot were not changed.

## Local correction — 16 October 2026

**Not delivered or installed.** The subsequently authorized live recipe is
recorded in the dedicated section below.
The historical 15 October live recipe below does not validate the new transport.
Base: PageQuay 1.1.0, commit `c6c2ee5`, with uncommitted local changes; Python
3.14.7, Playwright 1.63.0, Pillow 12.3.0.

Binary CDP IO and internal image Base64 were replaced by bounded BYOB integer
blocks from a Chromium fetch. A controlled empty document is fulfilled at request
stage without an encoded body; a second browser GET is validated again before
consumption. Its bytes are the artifact's original representation; a fresh HTML
challenge or changed source can fail this GET. Network guards, project isolation,
permissions and ordinary download denial remain active. No screenshots for image
acquisition. Human waiting and explicit resume retain the same job and tab.

The decoder runs in a disposable child, with pixel/input/CPU bounds and confirmed
exit on cancellation. No OS RSS ceiling is claimed on macOS, where the attempted
memory limits were rejected. Cleanup errors retain preceding errors and resource
IDs; unpublished artifacts are removed from the catalog before physical deletion.
The client refuses services lacking the new OpenAPI transport marker, supports
--job-id / --resume and never replays an uncertain acquisition POST.

Validation: **98 targeted tests passed**, starting at
2026-10-16T15:16:56.468226+02:00 (81.90 s). Final general suite: **307 passed,
104 skipped**, starting at 2026-10-16T15:21:17.089081+02:00 (12.20 s). These suites
overlap. Existing Starlette/httpx deprecation; Ruff, formatting, diff checks and
public OpenAPI equality pass. Tests use temporary profiles, databases and keys,
and loopback fixtures only. No installed service, real key/profile/database,
permissions, shared configuration, UniversRobot files, pause or schedule changed.
No commit, push, publication, dependency installation or service installation.

Private JUnit files: `/private/tmp/pagequay-image-isolated.xml` and
`/private/tmp/pagequay-regression-isolated.xml`. Test directories remain under
pytest retention; no global physical purge is claimed. Browser/socket resources
are closed by fixtures; physical removal failures are simulated.

Exact commands, intermediate failures, expected/observed outcomes, known causes,
unknown early timestamps and available tool/job log IDs are recorded in the
[French correction section](DOWNLOAD_IMAGE_REPORT.md#correctif-local--16-octobre-2026).
The subsequently authorized live recipe is recorded below. Git delivery and
installation still require separate approvals.

---

## Authorized live recipe — 16 October 2026, new transport

The exact user-supplied JSON was submitted through the real authenticated
PageQuay ASGI API in a disposable service, using a fresh visible Chromium
profile and default production source-network policy. Only Chromium contacted
the CDN. No installed HTTP listener, Tailscale or UniversRobot integration was
exercised. Command: `.venv/bin/python /private/tmp/pq-image-recipe-20261016.py`.

Successful run: 2026-10-16T15:28:36.340274+02:00 through
2026-10-16T15:28:54.580113+02:00, one acquisition POST. Job **completed**,
HTTP source **200**, exact final URL, no redirects, **689381 bytes**, JPEG
**1080 × 1530**. Authenticated artifact GET **200**, matching original bytes
and SHA-256 `f83f4625a8ee91ae51532e26ac5ee9044d0c972834a44815b7022fa32b4af38c`.
Anonymous GET **401**, other disposable project key **403** (expected denials).
Binary CDP body/capture commands and encoded synthetic bodies were forbidden.
No real Cloudflare challenge was observed.

Request `4bc0f52413c2728e98de34c0`, job
`df9aba01132ba4b65cfe3d6571a39409`, tab
`56b9f7b0f861d992addcbf34f662d702`, frame
`511FC28CF0A1283772F5859AF1F57051`, network request
`2ABD8FEDA829316FF2ECA4DF391239CB`, artifact
`c8e671ef2e756e07ad1530baaa6b5473`.

Tab closure, artifact catalog/file purge, zero active jobs/browser states,
database closure and removal of the disposable service directory were confirmed.
Private outputs remain in `/private/tmp/pq-image-live-g7_r1new/` (0700):
`report.json`, `audit.json`, `original.jpg` and final `recipe.py` (0600).
The JSON includes module hashes and audit log IDs. The service artifact URL is
no longer live after cleanup. No UniversRobot delivery or installation occurred.

The initial run at 15:27:37–15:27:52 +02:00 failed because the recipe script polled
every 0.25 seconds, exceeding the default PageQuay REST quota. HTTP **429** at
`job_poll`, report code `RECIPE_FAILED`, known cause: local polling frequency,
not the CDN. Job `f4fda08c6e3fb31bd507f1fc594ac753` was confirmed cancelled
before a separate recipe was launched at a two-second polling interval. No
uncertain POST was replayed. Failed poll request `54842d0b4c314bb01e967e48`,
audit `6e4ebee491118699525d646b49c26632`; private failure evidence remains in
`/private/tmp/pq-image-live-ffdvdjvk/`. The French report gives full reproduction,
expected/observed outcomes, versions, timestamps and IDs. No runtime repository
file was modified for the live recipe.

---

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
