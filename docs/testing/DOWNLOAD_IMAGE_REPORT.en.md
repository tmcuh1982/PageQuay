# GIF and originals up to 20 MB — local 1.2.0 validation

19 October 2026, Europe/Warsaw. The user approved implementation and isolated
validation after the read-only audit. **Local validation, before the subsequently requested release commit; no publication,
installation or dependency installation.** Base commit:
`42aa5d43763788c5ba5d6d27ad504cfdaf4d4562`, working branch `main`.
The four documentation edits already present were preserved. No UniversRobot
files, real projects/keys/profiles, shared quotas or LaunchAgent were changed.
Neither Dobot URL was fetched. Installed sources checked at the end still match
the initial 1.1.1 sources; a complete installed Git commit is not attested.

## Delivered behavior

The existing download_image endpoint, job lifecycle and receipt remain. No new
required receipt field. Strict integer max_bytes defaults to 5000000 and accepts
up to 20000000. Optional allowed_media_types is a closed, nonempty, duplicate-free
JPEG/PNG/WebP/GIF list; omission retains JPEG/PNG/WebP, null is refused. OpenAPI
1.2.0 adds x-pagequay-image-contract=original-gif-20mb-v1; the transport marker
is retained. Extended client requests qualify this marker before their single POST.

GIF87a/89a: complete structural walk through palettes, extensions, descriptors,
sub-blocks and trailer, then first-image decode only. No n_frames, animation
iteration, coalescing, screenshot, reencoding or preview. Logical screen and all
descriptors: ≤8192 per axis, ≤16000000 pixels, contained images, ≤1000 images.
The disposable validator has a 20 MB input cap, five CPU seconds and ten wall
seconds within the job deadline; cancellation/timeout kills it and confirms exit
within one second. Known GIF causes use fixed exit codes, without decoder output.

Existing guarded BYOB acquisition retains ≤64 KiB blocks and a sentinel, EOF,
length comparison, exact URL, HTTPS/TLS, redirects, public DNS/IP policy and
project isolation. Content-Range is also refused on HTTP 200. Artifact storage
accepts ≤20 MB images within existing quotas. Originals linked to their job
receipt use a bounded private GET: opened-file size check, recorded byte count,
≤64 KiB reads and sentinel, 30-second deadline, file closure, full HTTP 200 with
Range ignored. Other artifacts keep their existing path. Failures record safe
IDs/code/cause; pre-header JSON includes correlation and file cleanup status.
After headers, the binary stream aborts rather than becoming JSON.

The example client checks its expected project path, HTTP 200 without partial or
encoded representation, bounded blocks, size/SHA/MIME and a private temporary
output removed on failure. Existing-job resume and uncertain POST handling remain;
no automatic POST replay. Metadata files, module and OpenAPI declare work version
1.2.0; installed environments were not reinstalled to update package metadata.

## Validation and resource observations

| Check | Result |
| --- | --- |
| General suite, temporary loopback sockets allowed | 343 passed, 123 skipped, zero failures, 14.37 s |
| Targeted real Chromium suite, start 12:14:43 +02:00 | 164 passed, zero failures, 139.41 s |
| Targeted Ruff check/format, diff --check, offline lock validation | passed |

Suites overlap and must not be added. Final diagnostic/file-closure adjustments
were rechecked in the general suite; they do not change the Chromium transport.
The existing Starlette/httpx deprecation remains, without installing a new library.
Coverage includes exact valid GIF byte sizes 5000000/5000001/20000000/20000001,
valid PNG legacy size boundaries, missing/false lengths, misleading MIME/HTML,
encoding/partial responses, truncation after the first image, dimensions/frame
cost, decoder/private-GET timeout and cancellation, file mutation, isolation,
expiry, redirects/SSRF, explicit human resume and uncertain POST. Existing iframe
and TIMEOUT regressions remain; no iframe reader changed. Boundary fixtures are
real decodable images with legal GIF comments or PNG ancillary chunks and valid
CRCs, not arbitrary bytes appended after the image.

| Concurrent jobs | Bytes each | Acquisition + GET + checks | Sampled test-tree RSS peak | Stored before cleanup |
| --- | --- | --- | --- | --- |
| 1 | 20000000 | 7.612 s | 1769392 KiB / 1.69 GiB | 20000000 bytes |
| 4 | 20000000 | 17.349 s | 2599152 KiB / 2.48 GiB | 80000000 bytes |

Observed around 12:12–12:13 +02:00, ps sampling every 250 ms of pytest and its
descendants, including Chromium and the fixture server. Summed RSS can double
count shared pages. This is neither server-only memory nor a guaranteed ceiling.
The single-job timing overlapped a separate unit suite and is not a controlled
benchmark. Four successful 20 MB jobs retained their hashes and the fixture
project's 80 MB artifacts were removed. Temporary pytest directories may remain
under their ordinary retention; no global purge or other-project cleanup occurred.

Current shared limits were not raised: four concurrent jobs, thirty admitted,
100 MB artifacts/project, global content TTL 60 min and retention 24 h (minimum
used for expiration). Project overrides must be qualified before live acceptance.

## Residual limits

No OS RSS ceiling for Chromium or the decoder on macOS. Application byte/block/
pixel bounds do not cap Chromium internal buffers, JSON overhead or total memory.
Later frames are checked structurally, without decoding their compressed pixels;
their decodability is not guaranteed. Text-only GIFs, trailing data and inconsistent
reserved graphical fields may be refused. This is not an antivirus check.
HTTP framing can hide bytes behind a falsely short Content-Length; only the
representation exposed by Chromium can be validated. Initial navigation checks
headers and a second GET acquires bytes; responses can differ, and initial HTML
navigation has no global browser memory ceiling.

Job timeout remains 120 s default, ≤180 s, including queue and human waiting,
plus up to 1 s decoder termination and 5 s tab/guard cleanup. Private GET has a
separate 30 s budget; the client checks between blocks with a 15 s HTTP read
timeout. After response headers, retain the job receipt and reject incomplete
size/hash; no replacement error JSON or automatic POST replay is possible.

Intermediate issues: preloaded HTTP mocks made iter_raw raise StreamConsumed;
identity-only iter_bytes(chunk_size=65536) and true-stream tests resolved it.
A new file-mutation test captured a list before resetting it; the test was fixed.
Sandbox socket denials caused PermissionError and a derived startup timeout;
rerunning with temporary loopback sockets allowed passed. Exact times of first
intermediate failures were not instrumented and remain unknown. No installed job
IDs exist for those tests, and no installed service outage is inferred.

Exact commands and the complete French report are in
[DOWNLOAD_IMAGE_REPORT.md](DOWNLOAD_IMAGE_REPORT.md). Private evidence is under
/private/tmp/pagequay-gif-20mb-audit/: JUnit, sampled measurements, installed-source
hash comparison, implementation.patch and its manifest. The patch excludes the
four documentation changes already present before this work.

An intermediate general run also failed the existing audit-rate test
`test_denied_request_storm_keeps_exact_counts_and_bounded_detail` with 60 rows
instead of ≤30. The limiter uses one-minute monotonic windows; a boundary crossing
is possible, not proven by that run. No telemetry/quota code changed. The final
general rerun passed; the exact first-failure time was not retained and no
installed job ID exists. See the French report for the isolated reproduction.

Structure references: [GIF89a specification](https://www.w3.org/Graphics/GIF/spec-gif89a.txt)
and [Pillow GIF support](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#gif).

## Proposed Dobot acceptance — separate approval, not executed

Use a disposable 1.2.0 runtime, isolated profile/database/project and a private
short-lived key for that runtime only, content:read + browser:interact. No shared
service installation or restart. Sequentially acquire the supplied public
item41.gif and item43.gif URLs, exact expected_url, max_bytes=20000000,
allowed_media_types=["image/gif"], timeout=120, one POST each. Proposed batch
budget: six minutes including private GET and cleanup; ≤40 MB original storage.
Record actual timestamps/timezone, version/commands, source/final HTTP, SHA256,
bytes, first-image dimensions and available IDs; none are invented in advance.
Human CAPTCHA stays within the budget or fails, without bypass. An uncertain
POST is never replayed; no direct HTTP fallback. Clean only the disposable
runtime's resources and report any unconfirmed cleanup. No consumer PNG or
UniversRobot integration is part of this PageQuay acceptance.

Git delivery and installation require distinct approvals. Proposed branch:
codex/gif-20mb, with review of the exact patch and pre-existing documentation
edits. A later installation needs fresh service inactivity evidence, backup,
qualified prerequisites and rollback. Inactivity is not assumed now, and this
report does not establish that reinstallation is necessary.

---

# Previous history — unchanged

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
