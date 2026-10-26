# Navigation, challenges and extraction scope — PageQuay 0.2.2

[Français](NAVIGATION_SCOPE.md) | [English](NAVIGATION_SCOPE.en.md)

## Contract

Navigation and extraction are separate. allow_redirects defaults to true independently of expected_url/respect_robots. Navigation follows network-approved intermediate destinations, waits passively for recognized automatic checks, then compares the full final URL to expected_url **before title/business content reads**. Domain/prefix approval is never inferred.

```json
{"url":"https://example.org/start","expected_url":"https://example.org/document","allow_redirects":true,"respect_robots":true}
```

Mismatch: failed job, scope_changed (typed 409), details.target_url without query/fragment plus full-target SHA-256. details.navigation.final_url retains the exact observed destination for authenticated review. Frame diagnostics remain separate and never contain URLs/content. No business artifact is created. The tab retains its original expectation; omitting expected_url later does not approve the new destination. Approval must be explicit in a new call; the example never automatically adopts it.

False explicitly requires HTTPS/443 and refuses different targets before following (HTTP REDIRECT_BLOCKED); routing denies different main navigation. Different url/expected_url at admission yields URL_MISMATCH. With true, they may differ because expected_url is the final destination.

## Waiting and resume

Detection distinguishes explicit human intervention (CAPTCHA/requests/known frames) from automatic checks. Main response cf-mitigated: challenge also prevents capture of customized Cloudflare challenge pages. That signal remains tied to the displayed document until a replacement main response commits; request start/hash/history does not clear it. DOM recognition is conservative and not exhaustive.

Automatic waiting uses remaining navigation budget (default 30 seconds from goto), polling passively every 250 ms. No solver/click/reload/navigation retry. Explicit human demand or exhausted automatic wait moves the **same job** to waiting_for_human. Tab/URL and optional diagnostic screenshot remain available. PNG requires the existing screenshot scope and is not a business export.

```http
POST /v1/projects/{slug}/jobs/{job_id}/resume
Authorization: Bearer <original key>
```

After manual server-browser action, resume rechecks challenge and final URL. Persistent challenge waits again; another target fails scope_changed. Capture checkpoints are taken after waiting, so a legitimate human reload alone no longer triggers NAVIGATION_CHANGED. Extraction rechecks before publication; challenge during reading discards the unpublished snapshot and resume takes a fresh one. Other navigation changes remain denied; WORLD_NOT_FOUND is not globally retried or hidden.

Default shared human deadline 120 seconds per job, global job budget 180+120 seconds, resume authorization, locks, reader budget 10 seconds/frame and node/frame/byte quotas remain. Resume adds no new automatic budget. download_image has its own shorter total deadline as documented separately.

## Network, robots and callers

Redirects retain routing/CDP/public-IP proxy checks for credentials/ports/private or mixed DNS/rebinding/IPv6, Service Workers and WebSockets. expected_url or disabled redirects require HTTPS/443. Strict child-frame denial (strict_subframe_network_unattested) remains; not every OOPIF redirect is certified.

respect_robots no longer implicitly disables redirects. Initial rules are checked before navigation; a different approved final URL is rechecked before business reads. Extraction requires evidence for the current URL when enabled. No explicit refusal is bypassed. The robots helper separately denies redirects; its evidence is not transferred.

REST create/navigate, WebSocket, console and search use Navigate's default true. examples/acquire.py defaults to true; --no-allow-redirects explicitly denies and --expected-url declares approval. --resume controls only the saved job after manual action. Recovered checkpoints preserve their original payload, including old false. httpx.follow_redirects=False governs API transport and stays unchanged to avoid forwarding Bearer across origins.

## Separate validation

Chromium regressions cover automatic waiting/redirect, custom Cloudflare signal, wait exhaustion, unresolved resume, same-job navigation/extraction resume, scope change after intervention, no implicit adoption, invalidated capture and private redirect denial. False-mode tests still prove the target is never requested. Local-port exceptions are injected only into fixtures.

These fixtures simulate challenges; no real Cloudflare CAPTCHA is solved. Separate live KUKA validation confirms f1 CDP selection without showing a causal redirect relationship. [KUKA evidence](KUKA_FRAME_FIX.en.md). Installed private-key validation remained assigned to UniversRobot.

## Historical verified delivery

0.2.2 was deployed to /Users/lolo/Library/Application Support/PageQuayService after zero active jobs, with private backup /private/tmp/pq-navigation-022-backup-_vjth5ei. Ten source hashes, editable package and package/module/OpenAPI 0.2.2 verified; no dependency change. Ready/login 200, admin on API 404, anonymous API 401. Served/committed public OpenAPI matched; api_keys/projects/settings matched backup. No installed Bearer created/replaced. Restart invalidated old tab IDs.

Final historical suite: 265 passed, 4 skipped (headed minimization and three live engines). Final additions: 48 targeted plus five Cloudflare/browser regressions, overlapping sets. Ruff/format/offline lock/diff passed. A concurrent macOS restore test failed, then passed alone and in the sequential full suite. Internal OpenAPI generation was fixed and committed/served equality regression added. Logs: /private/tmp/pq-navigation-022-tests.log; deployment.json in the backup. This historical delivery record claimed neither remote push nor private-key installed UniversRobot test.
