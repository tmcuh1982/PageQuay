# Exact acquisition and frame diagnostics — additive 0.2.0 contract

[Français](ACQUISITION.md) | [English](ACQUISITION.en.md)

Bearer authentication, projects/scopes, historical formats, DuckDuckGo cursors and old search idempotency hashes remain compatible. The client server needs no browser. [Python example](../examples/acquire.py), [OpenAPI](openapi.json), [evidence](testing/ACQUISITION_REPORT.en.md). Since 0.2.2, automatic waiting, human resume and scope checks are separated from extraction: [navigation contract](NAVIGATION_SCOPE.en.md).

## Navigation and acquisition

```http
POST /v1/projects/{slug}/tabs
Authorization: Bearer <key with browser:interact>
Idempotency-Key: <persist before sending>
Content-Type: application/json

{"url":"https://example.org/document","expected_url":"https://example.org/document","allow_redirects":true,"respect_robots":true}
```

202 returns job_id, reserved tab_id, project, client_id (key ID, never secret) and job url. IDs remain correlated after failure/human wait; queue cancellation may leave a reserved ID without a created tab. Original HTTP request_id is persisted by migration 007. Existing-tab POST /tabs/{tab_id}/navigate supports the same options/idempotency header.

expected_url compares the entire Chromium-serialized URL, including an origin's trailing slash; no domain/section/prefix approval. It describes the final destination after challenge resolution. allow_redirects=true is default and permits a different starting URL; false requires matching url/expected_url at creation. False refuses different HTTP targets at response headers before follow/read, producing REDIRECT_BLOCKED with origin/path and full-target SHA-256, without query/fragment/credentials. Routing also denies script navigation to another main URL. Local hash/history changes are detected during capture; DOM mutation is not guaranteed to be blocked beforehand.

Strict navigation (expected_url set or redirects disabled) requires HTTPS/443. Legacy payloads preserve HTTP/HTTPS 80/443 and redirects. Extraction supplies its own exact expectation:

```http
GET /v1/projects/{slug}/tabs/{tab_id}/content?format=structured&expected_url=https%3A%2F%2Fexample.org%2Fdocument
Authorization: Bearer <key with content:read>
```

The tab lock serializes API work; navigation/frame revisions are checked before/after reads and between frames. Any navigation begun during capture, including same-URL reload, invalidates it with NAVIGATION_CHANGED. If a recognized challenge appears, the unpublished capture is discarded; the job waits then takes a new capture. The same isolated CDP context is reverified after each read. A different final URL yields scope_changed for review, without implicit approval transfer. No mixed-navigation artifact is published. Frames are sequential snapshots; ordinary DOM mutation is not frozen, so the response is not atomic across all documents.

## Document and artifact evidence

Navigation results, extraction results and structured JSON include:

| Field | Source/meaning |
| --- | --- |
| requested_url / final_url | Observed main request / current Chromium URL |
| http_status / http_status_reason | Main HTTP response, or null with explicit reason |
| content_type | Nullable main-document HTTP header, never inferred from DOM |
| redirect_chain / redirect_chain_truncated | Observed main 3xx responses, at most 20 |
| observed_at / navigation_id | Main-frame commit UTC ISO timestamp / unique local ID |

An “Error 500” title in HTTP 200 preserves the observed 200 without claiming business success. Chromium error DOM/set_content without a response never gains an inferred 200. A CAPTCHA may have real HTTP 200 while still waiting_for_human; its DOM is not automatically exported. Waiting results retain screenshot and HTTP evidence through timeout/cancel.

Structured JSON also includes captured_at, artifact_id, robots and network_policy. Artifact media_type/download Content-Type describe the produced file (application/json for structured), independently of source Content-Type. Existing node/frame/byte/storage/TTL limits remain; oversized complete JSON fails 413. Page text does not establish HTTP status, robots evidence or XPath.

Blocks have node_id and provenance.xpath built from real DOM parents/siblings in the isolated world: *[n], text()[n]. The path may identify a source node omitted from the optional tree. Shadow DOM XPath is null with xpath_reason=shadow_root. Depth/sibling bounds are explicit; references are snapshot/frame-local, may become stale and never cross documents.

## Public destinations and refusals

Routing validates URL/credentials/ports/DNS; every A/AAAA answer must be public. The proxy resolves again and connects to a **validated literal IP**, without intermediate resolution. Loopback/private/link-local/multicast/reserved, mapped IPv6/6to4/Teredo/known NAT64 and mixed DNS answers are refused. Rebinding to private is denied on next validation; existing tunnels stay pinned to their validated public IP. Remote WebSockets/Service Workers are blocked.

CDP redirect interception remains on the tab until close, including after domcontentloaded. Main-target redirect destinations are validated before follow; its subresources receive HTTPS/DNS checks too. Up to 32 routed refusals appear as bounded codes/causes in network_policy.refusals, without diagnostic URLs.

**Strict-mode limitation:** OOPIF redirect interception coverage is not attested, so all child-frame traffic is refused with strict_subframe_network_unattested and subframe_network=denied; affected exports set partial=true. Legacy mode keeps public iframes/proxy without claiming DNS revalidation for every OOPIF redirect in a reused tunnel. Cross-origin/OOPIF isolated extraction is independently tested in legacy mode. This opt-in restriction is not a general OOPIF coverage claim.

Evidence covers traffic mediated by these controls, not all internal Chromium/OS traffic, custom NAT64 or remote production networks. Private local ports are allowed only by test injection, without a production switch.

## Robots and user agent

The browser keeps native Chromium User-Agent. respect_robots=true reads /robots.txt in an owned auxiliary tab through guards/proxy and closes it in finally. Limit 65536 bytes, attested text/plain, Python RobotFileParser and the actual Chromium request agent. Disallow or HTTP 401/403 yields ROBOTS_DENIED before document loading. 404/410 explicitly permits on robots absence; other statuses/inconsistent type yield ROBOTS_UNAVAILABLE (429 retains RATE_LIMITED). Robots challenges require a human; if intervention changes the document, acquire again explicitly. Robots helper redirects are denied. Document redirects follow allow_redirects; an approved different final destination is rechecked before business reading, without transferring initial proof. Evidence contains status/time/type/observed agent/digest of parsed text. Default status=not_checked is **no robots evidence**. No exhaustive RFC 9309 compliance or non-robots policy coverage is claimed.

## Frame diagnostics

Legacy reason=frame_detached_or_unresponsive remains for compatibility and does not prove detachment. cause_code/diagnostic.cause distinguish FRAME_DETACHED, TIMEOUT, WORLD_NOT_FOUND, JAVASCRIPT_EXCEPTION, SIZE_LIMIT, SCHEMA_REJECTED, OTHER_ERROR. is_detached is a Playwright fact at failure, separate from exception indicators. Stages: visibility, cdp_session, context_selection, isolated_world, extraction, serialization, context_verification; monotonic duration, 10000 ms/frame and UTC timestamp.

Server logger pagequay.extraction emits frame_read_failure with request/job/tab/frame/artifact IDs, stages and original exception **types/codes** only. Arbitrary text/source lines are redacted: no query/fragment, cookie, Bearer or page body. Artifact IDs are reserved before reads, so failure logs may reference a never-created file. Rotate LaunchAgent logs. No page-JavaScript fallback, relaxed networking or global reader retry.

Old aggregate KUKA errors at 17:26 cannot be retrospectively diagnosed. The later 21:38 WORLD_NOT_FOUND was reproduced/fixed on the real site with bounded evidence: [KUKA fix](KUKA_FRAME_FIX.en.md). Its installed authenticated UniversRobot validation remained assigned to that client.

## Control, uncertain responses and quotas

Only the original key can control its job or close its newly owned API tab; local admin retains control and legacy unassigned tabs retain prior rules. Same project/scopes do not transfer ownership. IDs persist at admission; client_id is server key identity, not client-chosen text.

Cancel with POST /jobs/{id}/cancel, wait for terminal state, then DELETE /tabs/{tab_id}. Active/human-waiting work holds the lock; close returns 409, so cancel first. Failed navigation metadata remains in job.result. Ordinary acquisition does not silently close its tab on timeout/cancel; a merely reserved tab may return 404. Searches close only their own tabs. After service restart, active jobs fail without replay and restored tabs have new IDs without asserted old ownership. The separate download_image operation owns and closes its tab as documented in its contract.

Persisted-before-POST Idempotency-Key retrieves the same job/tab for 24 hours after lost 202; different payload/route returns 409. No automatic creation/retry. The example sends one creation POST and requires --recover for explicit replay or --resume after human action. A lost extraction GET response is separately uncertain: GET is not job-idempotent and explicit retry may create a second extraction, but no second navigation.

REST quota is shared per key across creation/poll/control/download/key-info: minimum key/project limit, fixed 60 seconds. Engine quota is separate: 6 attempts/60 seconds per project/engine, not a DuckDuckGo-imposed quota. 429 provides Retry-After if known; unknown capacity timing remains null with explicit cause/scope. Artifact quota exposes nearest expiry as a possible opportunity, not a guarantee of sufficient room. Engine partials/continuations follow [search](SEARCH_API.en.md). Poll/replay count as REST calls; no implicit creation retry, CAPTCHA solving or silent engine switch.

## Reader fix 0.2.1

KUKA WORLD_NOT_FOUND context selection is reproduced and fixed. context_selection distinguishes missing candidates/incompatible paths and records successful selection. Isolated worlds and network refusals remain. Installed validation with the private UniversRobot key is a separate recipe. See [evidence](KUKA_FRAME_FIX.en.md).
