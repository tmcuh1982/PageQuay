# Verification report — PageQuay historical record

[Français](REPORT.md) | [English](REPORT.en.md)

Initial run **October 9, 2026**, macOS Apple Silicon, Python **3.14.7**, Playwright Chromium **1243 / Chrome for Testing 153.0.8010.12**; exact Python versions in uv.lock. This English record preserves the historical outcomes and limitations; detailed chronological French evidence is linked through the language switch. Counts from overlapping runs are never additive. Later results do not retroactively turn earlier blocked recipes into successes.

Raw screenshots/navigation diagnostics stay local because they may contain machine names/network addresses/page content. Reviewed fixture JSON remains tracked. Current 1.1.0 release verification is in [its notes](../releases/1.1.0.en.md); the October 15 image recipe has a [separate report](DOWNLOAD_IMAGE_REPORT.en.md).

## Initial actual results

| Check | Result |
| --- | --- |
| pytest --browser --headed -q | 45 passed/one skipped, 52.79 seconds; optional external diagnostic skipped |
| lifecycle/jobs/proxy_shutdown after cleanup hardening | Four passed, 0.75 seconds; one new/three existing |
| live DuckDuckGo | Detected image-selection CAPTCHA, five-second human timeout, **no search results** |
| Browser after activity update | One passed, 46.86 seconds |
| Bearer OpenAPI | One passed |
| Ruff/format | 28 Python files conformant |
| zsh syntax / plist syntax | Four scripts and LaunchAgent pass |
| uv sync --frozen --extra dev | 44 packages checked |
| Disposable pq doctor | Browser/schema available, absent admin correctly reported |
| Process inspection | No test driver/Python/Chrome left |

47 distinct local tests validated, excluding external diagnostic; Starlette/TestClient/httpx deprecation remains unhidden.

Coverage: admin CSRF/login/origins/XSS/CSP/no-store/expiry/logout; Argon2id/hashed random keys/no secrets in listing/SQLite/rotation; project/scope isolation on tabs/jobs/artifacts/WS, one-use tickets/revocation; request/payload/job/artifact quotas; queued/active revalidation; invalid admin JSON without sensitive echoes; non-HTTP/private/metadata/tailnet/IPv6/ambiguous IP/mixed DNS/CONNECT refusal. Two visible Chromium profiles coexist with distinct cookies and flock/service exclusion.

Browser fixture exercises JS-rendered HTML/text/links/metadata/PNG, click/fill, private fetch/redirect with zero upstream requests, simulated challenge/wait/resume/protected screenshot, TTL preserving cookies, persistent soft restart, isolated crash/reset, idle restart, two-confirmation reset/replay refusal, cancelled-launch/proxy cleanup. UI was operated through login/projects/key/secret dismissal/dashboard/seven screens, no pageerror or global overflow at 390 px. Test-only LAN exemptions are injected, never production settings.

Live DuckDuckGo asked for images; no bypass/results invented. Google/Brave initially fixture-only. Desktop/mobile screenshots with disposable accounts were inspected. Outstanding target recipes included actual login/reboot/sleep, tailnet/ACL/outside-tailnet, interactive real admin, full restore/OS crash. No automatic destructive reset/snapshot/LAN exemption/upload/arbitrary download/MCP/webhook/CPU-RAM cap/application encryption. The proxy is not an OS firewall; external WebSocket denial may limit sites. This is reproducible MVP validation, not complete requirement compliance/security certification.

## October 10 — Google and MacBook Air client

Commands ran on the Mac mini (Mac16,11), not Air. Reverse SSH to Air port 22 was refused; no Air→PQ API success followed from that. Real visible disposable Google query “Playwright Python documentation” hit /sorry/index/reCAPTCHA and French unusual-traffic text. Initial UPSTREAM_CHANGED was corrected to challenge.required, then deliberate five-second human timeout. No result or found-page content downloaded; diagnostic browser text is not successful API extraction.

Live Google + detection tests: five passed/7.81 seconds; standard suite 49 passed/four skipped/2.67 seconds; targeted Ruff/client help pass. ASGI client was local. [probe_google.py](../../examples/probe_google.py) provides actual HTTP/client hostname capture, requiring reachable service/key; Air execution remained pending.

User confirmed ssh macmini-codex works Air→mini; that statement was not an executed remote API test. [probe_via_ssh.py](../../examples/probe_via_ssh.py) plus [serve_ssh_probe.py](../../scripts/serve_ssh_probe.py) create temporary isolated profile/key/service/tunnel for at most 15 minutes, with optional human resume and returned reports. No permanent service/system access is installed.

Actually run on mini: readiness, anonymous 401, key-free report/clean shutdown/closed socket. Direct https://playwright.dev/python/docs/intro through authenticated HTTP yielded navigation/extraction/download of **3821 characters**, not a Google result or Air test. Local ssh-probe-local report/text, Ruff/CLI help pass. Air command still unexecuted.

## October 10 — structured DOM

Delivered structured/include_dom JSON 1.0/private artifact/OpenAPI, no added package. [Contract](../EXTRACTION.en.md). Full headed excluding unchanged UI: **56 passed/two skipped**, 32.42 seconds. After bounds adjustment: structured/OpenAPI **eight passed**, 17.84 seconds including 5000 hidden elements. Ruff/format/Node syntax/offline wheel and extracted-wheel import pass. Real direct official page structured round trip on mini: **34 blocks/98774 bytes**, no truncation in that pre-final-node-count run.

Complex fixture covers hydration/ARIA/main/nested lists/HTML+ARIA tables/spans/form labels/external controls/JSON-LD/open shadow+slot/closed omission/cross-origin and hidden iframe/canvas. Private values/scripts/hidden nodes excluded; scope and incompatible option/unknown format/bounds/malformed inputs checked; javascript/data links excluded. Parsed rendered HTML misses shadow/iframe text; JSON recovers it. [Compact](structured-complex-compact.json) / [DOM](structured-complex.json): **5593/12390 bytes** unindented with identical semantic collections. Optional DOM is for inspecting relations.

The direct-page report/content remained local; no Google/Air success claimed. Explicit waits/actions/screenshots are still needed for unloaded/virtualized/closed/pixel content, no OCR/automatic interaction.

## October 10 — publishing

Preparation: **50 passed/ten skipped**, 2.61 seconds, Ruff/format 47 files, CLI remote-root help pass, no new intermachine test. Initial doc-only link check passed but app write returned 403 Resource not accessible by integration. After user-authenticated GitHub CLI login tmcuh1982/helper setup, first push advanced **5e85c7b→ad0c861**, remote reference verified. Earlier “not published” statements describe historical attempts. Publication changed no runtime or Google/Air/deployment recipe.

## October 10 — local administration and automatic start

Two-loopback-port CLI, actual-destination enforcement independent of Host/forwarded/cookies; standard **51 passed/ten skipped**. Admin/session/mutation/assets/WS refusal and Bearer health/API checks pass. Three initial sandbox socket failures disappeared when local sockets were permitted.

User LaunchAgent local.pagequay.gateway installed with RunAtLoad/KeepAlive and runtime under ~/Library/Application Support/PageQuayService to avoid Documents access restrictions; data separate under ~/Library/Application Support/PageQuay. Real checks: login 8765=200, API ready 8766=200, admin/login on API=404, anonymous API=401. No real admin auto-created. At that point Serve was not yet enabled, Air/ACL/reboot untested.

## October 10 — login CSRF

Safari reported Invalid login CSRF; exact initial cookie cause was not inspected. New pq_login_nonce under /admin avoids old Secure-cookie interference; nonce stable across forms; missing/stale mismatch returns fresh French form/403 without login, foreign origin denied. **53 passed/ten skipped**, full disposable Chromium UI one passed. Old Secure cookie/two forms/stale rejection/recovery covered. Runtime restarted; no-password real HTTP checks crossed CSRF and rejected intentionally oversized username with 400 before credential checking. Real-account Safari login remained the user's task.

## October 10 — API key UI/security/info

Creation UI explains fixed-window accounting/effective project cap/429; expiry off by default, disabling clears date and sends expires_at:null. Empty disabled text field avoids Safari's misleading datetime placeholder. Chromium tests verify expiry on/off/persistence/dated key/mobile overflow; screenshots inspected. Static assets deployed live; actual Safari blank disabled “Sans expiration” verified, API admin still 404.

Security editing adds admin GET edit/POST update with name/scopes/quota/expiry, preserved secret/project/counter, revoked edit denial, explicit expired-key recovery, targeted cancellation and key.updated audit. **63 passed/ten skipped**, UI one passed. Ten new cases cover CSRF/auth/validation/no partial writes/scopes/quota/expiry/revocation/cancel. Explicit aria-label fixed an ambiguous disabled project label; mobile table scroll preserves actions. Runtime zero-job restart/readiness/isolation pass; real key settings unchanged.

Calling-key GET /key-info returns only public own identity/project/scopes/nullable expiry/configured-project-effective limits/remaining/reset UTC, typed OpenAPI/no-store, shared quota and no admin-session substitute. **70 passed/ten skipped**, Ruff/format 52 files/schema/Bearer pass, seven new permission/isolation/counter/update/expiry cases. Standard-library client refuses API redirects to protect Bearer. No UI/browser rerun. api.py/models.py deployed after zero jobs; ready/login200, anonymous401, API admin404, real key metadata unchanged; Serve not enabled by this patch.

## October 10 — Tailscale diagnosis/activation

Mini loopback/API healthy; Tailscale Running/ShieldsUp=false, no initial Serve/Funnel. Exact hostname local checks passed. serve --bg waited for tailnet enablement. Safari initially used an Apple account in another empty tailnet, so correct GitHub-tailnet login was requested. User enabled Serve; first command saw concurrent etag conflict, then current state verified: persistent private HTTPS443→127.0.0.1:8766, no Foreground/Funnel/admin route.

Normal-TLS same-mini requests returned ready200, anonymous key-info401, admin/login/static404. No credential/certificate bypass. **Another-device/ACL/reboot still not tested.** No software suite needed for network enablement.

## October 10 — minimized windows

Standard **73 passed/11 skipped**; headed UI/browser **three passed**. Startup setting/local buttons/new-tab preservation/native minimize/restore/project isolation/navigation/actions/content/PNG covered; screenshots temporarily restore/minimize and were inspected. Ruff/format/diff pass; zero-job runtime restart/readiness/admin isolation pass.

## October 10 — DuckDuckGo 0.2.0

Full headed **116 passed/three skipped**, 72.84 seconds, with fixtures for three native pages/remainder/provenance/rank/duplicate/repetition/cursor binding/expiry/use/shared quotas/idempotency/SQLite reopen/challenges/cancel/retention/cleanup. Real Chromium native POST handles repeated/Unicode fields through proxy. Client uncertain-receipt/checkpoint/path/Bearer/header/retry tests; final CLI/checkpoint subset **five passed**. Ruff/format/schema/link checks pass.

Live three queries (robot agriculture/fr-FR; agricultural robotics manufacturers/en-US; robots agricoles France/fr-FR) all hit CAPTCHA, challenge.required, five-second human timeout and cleanup. **No live result, no proven three-page upstream pagination.** Raw reports/HTML remain ignored. Sixteen runtime files/migration003 deployed after backup/zero jobs; keys/projects/caps preserved (10 results, six engine attempts/60 seconds). Local/private HTTPS schema/readiness200, anonymous search401/admin404. Private reference-client search was not replayed without its key; live recipes used disposable services.

## October 10 — repeat mini recipe

Full headed **116 passed/three skipped**, 71.06 seconds, Ruff/format 58 files. Initial sandbox socket failures were environmental, no service fix. 27 installed sources/assets/migrations matched checkout. Loopback/private HTTPS status/schema/isolation passed, Funnel off; no Air/reboot test. External diagnostics first **two passed/one failed**, with Google UnboundLocalError after cleaned-up tab. Conditional screenshot fix yielded Google **one passed**, 7.82 seconds. Google/DDG still human-blocked, no results, zero search tabs.

Independent direct Playwright docs API path succeeded: text **3832 bytes**, structured **20719 bytes**, disposable service/profile closed. Dashboard inspected. Generated fixture ports/dates/IDs restored; real data/settings untouched and existing service left running.

## October 10 — external port, filters and CLI lookup

External HTTPS form: general **126 passed/14 skipped**; dedicated **20 passed** (types/ranges/admin/CSRF/conflicts/shared/Funnel/temporary/stale edits/rollback); Chromium **one passed** with simulated Tailscale, 443→8443/initial activation/desktop-mobile. Actual Serve443 read only; no arbitrary real port change. Runtime readiness pass.

DuckDuckGo region/time_range added to API/UI/client/checkpoint with native kl/df/cursor/idempotency binding and additive migration004 preserving old records. Explicit filters rejected for auto/Brave/Google. General **142 passed/14 skipped**, 6.45 seconds; transport/UI each one passed after fixture selector/project/callback corrections. Ruff/format/Node/diff pass; no real filtered search/date-verification claim. Nine runtime files match; initial bootstrap error5 recovered; ready/schema/login/isolation pass, real config/profiles/keys preserved.

Disabled Apply under LaunchAgent: minimal PATH directly invoked Tailscale.app producing non-JSON CLIError3 with exit0; /usr/local/bin wrapper worked. Prefer normal macOS CLI directories before app fallback, preserving PATH priority. Two regressions; external/security **41 passed**, Ruff pass. One module deployed/zero-job restart; actual Safari detected URL/enabled Apply, retained typed8443, no route mutation.

## October 10–11 — audit

Migration005 adds JSON detail without losing old events: real navigation/resource/redirect URL, encoded bytes/status/job/tab, function actions/pagination “next page”, early actor capture/manual browser attribution. Initially query/fragment/userinfo were removed. General full Chromium **159 passed/four skipped**; database upgrade/redaction/admin/XSS/filter/unavailable/cancel/gzip/redirect/native POST/private refusal/manual attribution/UI cases pass; static screenshots inspected. Eight runtime files deployed after backup/zero jobs; ready/login200, anonymous audit303, API audit404/key-info401.

**Later explicit user change supersedes initial redaction:** queries/fragments retained exactly (including repeated/empty/encoded parameters); userinfo remains removed. Old [masque] values cannot be reconstructed. POST/input/cookie/raw messages remain excluded. Six audit/UI tests, Ruff/diff pass; two runtime files deployed/backed up/restarted, expected status codes pass.

Permanent horizontal “Colonnes” range/arrows synchronize actual scrolling, keyboard/limit controls and responsive width. Chromium desktop/mobile/rightmost column/no document overflow/JS errors verified; screenshots/Ruff/diff pass, three assets hot-deployed without job interruption.

Job filter becomes native select of 200 recent jobs, preserving explicit selections beyond the list. Uniform 42px fields, second-precision datetime-local, browser-local display/UTC serialization, offset support/legacy naive UTC/inverted-range refusal. last10min/lasthour/Today preserve other filters; Today local midnight→click time. **26 targeted tests** cover inclusive bounds/offsets/select/uniform height/presets/15:20:30 Warsaw→13:20:30UTC/mobile/no errors. Four runtime files deployed after backup/zero-job restart, expected isolation codes pass.

Safari revealed grid/job labels still UTC while filters were local; only presentation changed to browser-local “Date locale”, with exact UTC/fuse in tooltip. **Seven audit/UI tests**, including 20:46UTC→22:46 Warsaw, presets/conversions. JS/template hot-deployed; Safari same filter/job verified, no timestamp/history changes.

October 11 durations: monotonic nested functions and request→finished/failed, excluding async body-size lookup overhead. Jobs timed from execution-slot acquisition, excluding queue/including human wait. Pre-execution cancels/historical missing values show “—”; details.duration_ms, no migration. **14 audit/jobs/UI tests** pass; desktop/mobile/rightmost column inspected. Four runtime files/private pq-audit-duration-pfal2l3w backup/zero-job restart; isolation/readiness pass, no real project/key/network changes/push.

## October 12 — local API port

Local settings 1024–65535, independent of Serve; strict type/conflict/admin/CSRF/stale-edit checks, atomic 0600 local-api.json override, active/saved/pending restart distinct. CLI serve/doctor/create_app read it; cancel by saving active port. No Serve route change; adapt destination separately. General **176 passed/15 skipped**, local/external final **38 passed**, Chromium one passed; form without Tailscale, JSON/persistence/warning/desktop-mobile, loopback/admin denial/anonymous401. Five runtime files/backup pq-local-port-backup-gkdviy_l/restart hashes/statuses pass. Actual8765/8766 preserved, no real override/key/project/route/push.

## October 12 — security/resource fixes

Final normal **186 passed/16 skipped**, 9.57 seconds. Structured/audit/budgets Chromium24, final budgets11, byte cap10/one skipped, jobs/local22, overlapping. Ruff/format53/Node/diff pass. Cases include 300 anonymous401 counted while detail≤30/alert, queues/reserves/rows/bytes/task limits/writer failure/retry/cardinality, hostile prototypes/title512/truncation/HTML-text413/surrogate/partial/frame anchor/one-time migration.

Full headed initially **194 passed/five failed/three skipped**; four async-flush audit assertions adapted and rerun. Remaining native macOS minimize/navigation failure reproduced on pre-fix backup sources as Browser.getWindowBounds timeout before new readers. **198 distinct pass, no fully green complete headed suite/minimization claim at this stage.** Later 0.2.4 full suite below is separate. Warning retained.

Nineteen runtime files/migration006 deployed after zero unfinished jobs/source-SQLite backup; hashes/readiness/login/schema/budgets/counters verified. No profile/key/project/port/external-route change. Audit may omit detail under saturation; logical caps do not bound SQLite physical size or native Chromium/driver/crash buffers.

## October 14 — release 0.2.4

Explicit loopback CDP through Playwright-pipe relay; preserved guards and native ws/wss refusal through second proxy. Real Chrome/Chromium positive controls/refusal/no handshake/frames/popups/workers/native constructor/continued HTTP/HTTPS/no direct fallback after listener stop; endpoint/startup/handler cleanup covered.

Final PQ_BROWSER_TESTS=1 pytest: **343 passed/four skipped**, 95.71 seconds, existing warning. Targeted Ruff/format/offline lock/version/diff pass; isolated test profiles preserve installed demo session. Installed fresh Chrome/Chromium search/Yamaha P-45 then five searches/five products in one retained Chromium session all HTTP200; first Fender click timed out, navigation to observed links succeeded. No observed challenge, no guarantee/future solving claim. [Detailed protocol](../BROWSER_TRANSPORT.en.md).

Generated fixture port/date/ID changes excluded. No raw report/profile/backup/secret/capture tracked. Historical deployed runtime retained 0.2.2 metadata; 0.2.4 source preparation did not restart the service.
