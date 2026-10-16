# KUKA iframe WORLD_NOT_FOUND fix — PageQuay 0.2.1

[Français](KUKA_FRAME_FIX.md) | [English](KUKA_FRAME_FIX.en.md)

## Result

Reproduced/fixed on https://my.kuka.com/s/?language=en_US through a disposable HTTP/ASGI PQ service with ephemeral Bearer, production public proxy and Chromium, without installed profiles/keys. The user assigned later installed-key validation to UniversRobot.

Final live export: exact final URL, **69 main blocks, f1 extracted, partial=false, truncated=false**, no frame limit. Selected document “KUKA - player” matched the frame URL but had no mounted text blocks (nine visited/two included nodes). Complete means a mounted DOM snapshot within limits, not invented visual/application data. The recipe explicitly waits up to ten seconds for iframe then five seconds hydration before one extraction. Navigation without a mounted frame does not validate this bug.

## Reproduced cause and fix

Before: two CDP contexts, expected path [2] from parent.child_frames.index(frame), isolated paths [0] and []; still attached, failed in about nine ms at context_selection/WORLD_NOT_FOUND. Playwright attachment order is not native window.frames identity; DOM order is not generally interchangeable either. Chromium regression inserts an already-added iframe at the DOM start while native order differs. KUKA used a page session with cross-origin same-site child, not evidence of site-specific OOPIF failure. A separate regression covers an internal OOPIF descendant.

Fixed pq_frame_slot selector is registered before browser creation with content_script=True. It maps native window[i] to iframe/frame owners, then ElementHandle.content_frame checks exact Playwright identity. No URL/title matching or DOM writes. Selector runs in isolated utility world; extraction remains isolated CDP, never page-owned JavaScript. Hostile page monkeypatches are tested.

Reader resolves the frame's own or nearest owning ancestor CDP target; internal OOPIF descendants no longer fall back to main-page target. Only the expected “no separate CDP session” error continues resolution. Path/identity/context are rechecked before/after capture. Failures remain unavailable/partial, never forced complete.

Budgets preserved: ten seconds/frame, four documents/export, 128 CDP candidates, path depth 32, existing bytes/nodes/proxy. Identity inventory max 128 slots/owners; open shadow exploration max 2000 elements. Large unrelated DOM is not copied or charged as frame owners.

context_selection includes session type, candidate count, expected/selected paths, at most eight observed paths of 32 integers, truncation and no_candidates/path_mismatch cause. No page body/URL/query/fragment/cookie/Bearer. Server success/failure events include version and correlation IDs; arbitrary exception text remains redacted.

## Correlated live traces

Before: request 844fb935ea2823f26458f597, job c88ada640d410864cd2abb1050a1a176, tab f9766c05e5a0986f49286df992600ff8, artifact 51e67491222ac01d81cf7f9a3db97cd8, frame f1, attached, WORLD_NOT_FOUND/context_selection, page session, two candidates, expected [2], observed [[0],[]], path_mismatch.

Final 0.2.1 success: 2026-10-12T20:05:01.931232+00:00 (22:05:01 Europe/Warsaw), request 0eb1a5ac5483988332959676, job 64e31857d3201278ff161cab6d8bfbfd, tab cebf49c37576b61e084c366b7b279a7d, artifact 390f03a9aad543f474b90906cb6a87cb, f1. context_verification took 24.409 ms of 10000; attached, page session/two candidates, expected/selected [0], observed [[0]], no failure/truncation, path_source=isolated_frame_owners.

Private before evidence: /private/tmp/pq-kuka-real-ttkoaw7e/frames.log; after: /private/tmp/pq-kuka-real-gmkxjspo/{frames.log,summary.json,artifact.json}. Disposable IDs are not downloadable from installed API. Original UniversRobot trace was also found in LaunchAgent log at 2026-10-12T19:38:28.381257+00:00. No real page body/secrets shipped.

## Validation and historical deployment

Global Chromium: 249 passed, four skipped (headed minimization/three live engines). Final inventory adjustment: 33 targeted passed, overlapping. Simulations cover identity mismatch, OOPIF ancestor, missing/path mismatch, 128-slot bound and diagnostic redaction. Chromium covers DOM/native order, hostile scripts, OOPIF descendant, large hidden DOM, permitted redirects and legacy limits. Ruff/format/diff/offline lock pass.

0.2.1 deployed to ~/Library/Application Support/PageQuayService after zero active jobs: eight source files/package metadata, offline editable install without dependency change. Module/package/OpenAPI all 0.2.1. Private source/SQLite/metadata backup: /private/tmp/pq-kuka-021-backup-5gtr49vj, deployment.json hashes. Ready/admin-login 200, admin on API 404, anonymous API 401; public schema/source hashes match; api_keys/projects/settings match backup. No relaxed network rules. Restart invalidated old tab IDs. Private installed Bearer validation remained UniversRobot's task.

## Redirect option and independent 0.2.2 check

```json
{"url":"https://my.kuka.com/s/?language=en_US","allow_redirects":true}
```

Caller checks exact result.navigation.final_url before structured extraction. expected_url remains binding even with redirects; false refuses another target before acquisition. DNS/IP/port guards always apply. Strict HTTPS child-frame denial remains because all OOPIF redirects are not attested. This live recipe used legacy mode with explicit final comparison.

[0.2.2 navigation/challenge changes](NAVIGATION_SCOPE.en.md) are separate; no causal link to WORLD_NOT_FOUND is established. respect_robots no longer implicitly disables document redirects; its helper retains explicit refusals.

A new real 0.2.2 recipe with allowed redirects and exact extraction expectation again produced 69 blocks, f1 extracted, no partial/truncation and zero mounted player text. No real Cloudflare challenge was solved. At 2026-10-12T20:25:38.877649+00:00 (22:25:38 Warsaw), f1 context verification took 26.787 ms: request 14cdc846d3c4e3d87dbded52, job e4328c80962996a46a0e875812b6c272, tab 3d9d2e348b1819f12677e8b8c2e2ce61, artifact d360f3ee0ededa246a0a35aa0d3f99af. Page session/two candidates, expected/selected [0], observed [[0]], no failure/truncation, isolated_frame_owners. Private evidence: /private/tmp/pq-kuka-real-9506jh9f/{frames.log,summary.json,artifact.json}; not installed API resources.
