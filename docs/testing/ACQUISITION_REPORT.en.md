# PageQuay acquisition report — October 12, 2026

[Français](ACQUISITION_REPORT.md) | [English](ACQUISITION_REPORT.en.md)

Requested CHG-20261010-004 / frame diagnostic CHG-20261012-029. Additive Python/FastAPI/Playwright 0.2.0 extension, no new dependency/client browser. This is a historical delivery record; later [KUKA validation](../KUKA_FRAME_FIX.en.md) supersedes the initially unperformed real-site recipe, and 0.2.3 restores native User-Agent.

## Delivered

Main-document requested/final URL, nullable HTTP/reason, source Content-Type, bounded redirects/UTC/navigation_id, including structured artifacts and failed/waiting navigation. Opt-in exact URL, pre-follow CDP response-header redirect guard, persistent tab checks and isolated-context verification before/after capture. Strict HTTPS/443/public DNS/validated-IP proxy; strict child traffic denied because complete OOPIF coverage is not attested.

Reserved project/key/tab IDs at 202, persisted request_id (migration 007), idempotent create/navigation, close ownership, explicit retained ordinary acquisition tabs on timeout/cancel. Bounded opt-in robots (then-declared PageQuay User-Agent), actual-DOM XPath, artifact budgets and separate quotas. Distinct frame causes/bounded correlated redacted server logs with legacy reason retained; isolated FRAME_PATH across origins/OOPIF. [Contract](../ACQUISITION.en.md), [OpenAPI](../openapi.json), [private-checkpoint client](../../examples/acquire.py), explicit recovery/cancel/no automatic creation retry, 0600 files.

## Executed evidence

| Case | Evidence |
| --- | --- |
| Old payload/Bearer/scopes/pagination/idempotency compatibility | HTTP/legacy browser/search transport tests |
| Main 200/404/Content-Type, ignore subresource 200 | Acquisition unit and browser tests |
| Error DOM with no response | Real Chromium preserves null/reason |
| “Error 500” page actually HTTP 200 | Observed 200, no business-success inference |
| Cross-path/host denied redirects | CDP simulation and two-server Chromium; no target GET |
| Legacy allowed redirects | Main-document chain evidence regression |
| Concurrent navigation/same-URL reload | Simulation/Chromium NAVIGATION_CHANGED, no artifact |
| Human CAPTCHA/cancel/timeout/retained tab | Waiting/screenshot/HTTP evidence, explicit close after drain |
| Private/mixed/rebinding DNS, IPv6, empty userinfo | Existing network/new typed-cause cases |
| Lost 202 | ASGI/simulated browser executes once, correlated IDs, different payload 409 |
| Owner-only close | Two manager identities, existing job checks |
| Robots denied | Chromium proxy reads robots, never requests document, only helper tab closes |
| XPath | Normal-fixture paths resolve one real node; shadow has explicit null reason |
| Cross-origin/OOPIF FRAME_PATH | Chromium localhost→127.0.0.1 child plus multi-context simulation |
| Timeout/detached/missing world/JS/size/schema | Distinct stage/cause/duration/budget/is_detached/redacted chain |
| Correlation/no secret leaks | Injected-secret caplog checks and Bearer-free response/error |
| Engine versus REST quota/partial/continuation | Existing pagination plus REST limit/retry timing/one creation |
| Strict child denial | Test-only local injection, child not requested, typed cause/partial |

Commands/results: pytest -q **217 passed/27 skipped** before final two browser cases; acquisition/OpenAPI/structured/resource budgets --browser **51 passed**; acquisition_browser --browser **13 passed**. Ruff/format/two JS syntax/diff pass. Full --browser: **241 passed/one failed/four skipped**; audit fake job lacked kind after metadata retention. Runtime compatibility fix preserved the test; final audit+acquisition_browser **20 passed**, including prior failure. **242 distinct tests validated**, no known remaining failure. Four optional exclusions: headed native minimization/three live engines. Existing Starlette/httpx warning retained.

Local/ephemeral ports and strict-test HTTPS exemption are injected only in fixtures; production HTTPS/443 is separately tested. They do not represent all public HTTPS sites.

## Historical installed service

Fourteen files synchronized to ~/Library/Application Support/PageQuayService/src/pagequay after zero active jobs, private source/SQLite backup /private/tmp/pq-acquisition-backup-jo4wwihi and LaunchAgent restart. Hashes/migration 007 verified. Ready/login/API ready 200, admin on API 404, key-info without Bearer 401; public schema includes expected_url/FrameDiagnostic, no admin. No key/project/profile/port/Serve change; restart invalidated old tabs.

Final resync used /private/tmp/pq-acquisition-backup-kfx1trt0 after zero jobs, preserving failed metadata/fake-job compatibility. Final source/runtime hashes and readiness/isolation/schema rechecked. api_keys/projects/settings match first backup; served/committed schema identical.

## Remaining limits at that delivery

Real KUKA was **not yet reproduced**: existing agentderecherche secret unavailable (DB stores hash), no key replacement/bypass, user explicitly chose delivery without it. Old October 12 errors remained UNKNOWN; fixtures did not establish their real cause. Later live evidence is documented separately, without inventing retrospective attribution.

Strict mode denies child traffic; legacy mode does not claim DNS revalidation on every OOPIF redirect in reused tunnels. Navigation/context coherence is not multi-DOM atomicity or stable XPath after mutation. Closed parent shadow/pixel data are not exported. Robots is opt-in/bounded, not exhaustive RFC 9309; not_checked proves nothing. A robots challenge needs manual intervention and explicit reacquisition after document change.

Exception types/codes/stages are retained but arbitrary messages/source lines removed, limiting unknown-signature detail. Rotate LaunchAgent files. Capacity deadlines stay null; nearest artifact expiry does not guarantee enough room. JSON artifact integrity does not prove page truth. External engines/headed minimization/private UniversRobot/remote deployment require separate recipes; no such success is inferred here.
