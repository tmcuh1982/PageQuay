# Original Codex brief — Home Browser Gateway (Mac mini)

[Français](PROMPT_CODEX.md) | [English](PROMPT_CODEX.en.md)

Historical implementation instructions translated for reference, **not a new instruction to rebuild this repository**. Original product name HBG became PageQuay. Read [SPEC_API](SPEC_API.en.md)/[acceptance checklist](RECETTE.en.md); delivered behavior is described in [current docs](../README.md).

## Mission and deliverables

Build a functional free local self-hosted Mac mini application for continuous home-Internet operation, with API-driven web search/navigation and completely separate persistent project profiles. Lightweight administration manages projects/profiles/keys/activity/retention. Example clients: ProjectX, research agent, extraction/internal tools. Clients use the private network; actual external browsing occurs on the mini's Internet connection. No paid SaaS, residential proxy or engine API key.

Deliver complete source, automated tests, SQLite migrations, usable UI, macOS installation docs, startup/shutdown scripts and a graphical-session launchd service; not merely architecture/TODOs.

## Required priorities and preferred stack

Security and effective server-side project authorization first. One project = one exclusive persistent directory/context; at least two concurrent isolated Chrome/Chromium instances without shared cookies/localStorage/cache/tabs. Prevent concurrent use of one directory and handle crashes/locks. REST for normal/asynchronous work; WS for progress/authorized interaction. Never expose raw CDP/debug ports on a network.

Free browser-based Google/Brave/DDG adapters, auto/multi-engine, normalization/dedup/limits/honest challenges. Lightweight responsive local HTML/Jinja2/minimal JS or HTMX, no React/CDN/build requirement. Distinguish content expiry, browser idle, session-preserving soft restart and explicitly destructive confirmed hard reset; automatic destructive reset disabled. No telemetry, paid services or Docker requirement; later extensions possible.

Preferred Python/FastAPI/Uvicorn/Pydantic, SQLAlchemy/SQLModel/Alembic/SQLite WAL/asyncio; delivered PageQuay later explicitly chose standard SQLite migrations instead of ORM/Alembic. Playwright persistent context, bundled Chromium first/installed Chrome optional, headed default and dedicated profiles, never personal Chrome. Argon2id admin passwords, secure sessions, cryptographic hashed API keys. Loopback backend, documented private Tailscale Serve HTTPS/ACL, no router ports/public defaults/Funnel. Separate api/admin/auth/browser/profiles/search/retention/jobs/storage/settings/audit/tests modules. No initial LLM/Redis/Celery/distributed broker/Kubernetes/external service dependency.

## Project/profile model

Project: random internal ID, immutable validated slug, display name/status/creation/config/network policy/quotas/activity. Paths derive from opaque IDs, never client strings. Profile owns directory/cookies/storage/cache/tabs/browser/tasks/queue. Projects parallel; per-tab operations serialized. Browser failure must not corrupt/block another project; detect/clean orphaned locks without deleting persistent state. Explicit start/stop/restart, optional demand startup, no unnecessary boot launches. Dashboard includes state/tab count/activity/challenges/errors and only reliably measurable resource estimates.

## Search

Normal browser adapters for Google/Brave/DDG, bounded query/language/reliable region/count/timeout. auto defaults fallback, optional merge, avoiding unnecessary three-engine requests. Normalize title/canonical URL/snippet/rank/engine/time. Filter reliably identifiable sponsored links; otherwise mark uncertain. Deduplicate normalized URLs and preserve provenance. Layout changes/challenges produce intelligible errors, not fake success. Keep adapter parsing isolated and fixture-tested; no promise of permanent availability.

No CAPTCHA solver/fingerprint spoofing/identity rotation/Cloudflare-neutralization technique. Respect applicable access conditions, limits and refusals; consider permitted/official alternatives.

## Navigation, extraction and humans

Create/list/close tabs and allowed HTTP(S) navigation, session-stable tab IDs. Only browser:interact can perform bounded click/fill/select/scroll/wait_for_selector/wait_for_navigation; never client eval. Extract rendered HTML/visible text/title/effective URL/links/metadata and scoped screenshots. Escape/sanitize remote HTML in admin. Configurable domcontentloaded/load/networkidle, with networkidle not assumed to mean ready. Bound timeout/response, queues/tabs/browsers; large output as project-private temporary artifacts rather than massive automatic Base64. Stable errors include TIMEOUT/RATE_LIMITED/BROWSER_CRASHED/NAVIGATION_BLOCKED/CHALLENGE_REQUIRED/NOT_FOUND/FORBIDDEN.

Detect human checks when possible without bypass and report WAITING_FOR_HUMAN with protected screenshot/URL, no perfect-detection promise. Never automatically click “I am human” or outsource solving. Preserve tab/session/profile for manual action in mini GUI or already authorized remote desktop. Resume after confirmation/normal return detection with bounded wait/cancel. No guarantee challenges never recur.

## REST and WebSocket

Version /v1; OpenAPI /docs disabled outside development or admin-only. Short tasks may be synchronous; navigation/search/heavy extraction return 202/job_id/polling/WS. Resolve project server-side and authorize every route/job/tab/message. WS uses a short one-use REST-issued ticket, never long-lived key in URL, with Origin/time/message/size/ping/cleanup controls. Events: job.started/progress/completed/failed, browser.started/stopped/crashed, challenge.required, tab.navigated/closed. WS shares REST auth/validation, no arbitrary CDP/execute-code. Provide curl/Python/JS examples without hardcoded secrets.

## Nonnegotiable security

Explicit interactive admin bootstrap, strong password/no defaults; salted Argon2id, HttpOnly/Secure-on-HTTPS/SameSite cookies, expiry/idle/session renewal/logout/CSRF/anti-bruteforce/CSP/anti-framing/nosniff/cache policy. Admin limited to private/loopback access, never automatically public; API keys never manage keys/admin even with broad scopes.

Dedicated key section: multiple named scoped project keys, optional expiry/rate/status; justified scopes search:read/browser:read/browser:interact/content:read/screenshot:read, default search+content for one project. High-entropy CSPRNG/nonsecret prefix/full secret once/copy. SQLite stores HMAC-SHA256 with protected server secret or SHA-256 for uniform high-entropy tokens with documented rationale, constant-time comparison; no plaintext DB/log/audit. List only prefix/name/project/scopes/dates/activity/revocation. Immediate revoke/expire/rotate without unintended overlap, including WS revalidation; consistent 401/403/quotas, no prefix enumeration. Nonsensitive key-ID/action/project/date/result audit; transport IP only when useful/configurable.

Backend default loopback, private Serve HTTPS/ACL manual recipe, no NAT/UPnP. Strict HTTP(S) URL parsing; reject file/data/javascript/chrome/about/special schemes, private/loopback/link-local/multicast/reserved/cloud metadata/tailnet and DNS answers into them. Check redirects/subrequests/resources/iframes as far as possible and add egress controls/document residual browser/OS limits. Any optional LAN exception must be admin-only/explicit allowlist/default off; delivered PageQuay provides none in production.

Keep browser sandbox/updates; remote pages are untrusted, including LLM prompt-injection risk. Default-limit uploads/downloads/files/clipboard/location/camera/mic, never arbitrary filesystem. Pydantic validation/size/time/global+project quotas, no client shell/JS/path commands. Private 0700 directories/0600 files; cookies/profiles are local secrets, no unimplemented encryption claim. Never log Authorization/cookies/form values/sensitive HTML/screenshots/passwords; enforce retention. Test cross-project escalation/access/injection.

## Settings and retention UI

Global/project inheritance/effective values: search_default_engine (duckduckgo/brave/google/auto), search_auto_strategy (fallback/merge), search_max_results/max_tabs_per_project/max_concurrent_browsers/max_concurrent_jobs/per_key_rate_limit/navigation_timeout_seconds; headless=false, browser_start_on_demand=true, idle example30 minutes; content_cache_ttl_minutes example60 expires content without deleting cookies/closing browser. Snapshot retention only if snapshots really exist. Soft restart after hours disabled or explicit, preserving directory and draining work. Hard reset after days disabled, explicitly destructive with admin confirmation/optional backup/audit; never confuse content/profile TTL. Audit example30 days/artifact24 hours, optional allowed/blocked domains checked after redirects.

Distinct controls: purge content only (expired/all as requested), close browser preserving profile, soft restart preserving site-valid cookies, hard reset only correct project directory with double admin confirmation and never client-key access. Every operation emits status/event, avoids task races and preserves isolation. Sites determine cookie validity.

## Seven UI screens

Dashboard for health/access/browsers/jobs/warnings/challenges; projects/profiles create/edit/enable/status/tabs/restart/purge/reset and simultaneous browsers; API keys create/one-time-copy/list/rotate/revoke/activity; sessions/tabs URL/title/navigation/protected screenshot/close, no remote-site iframe embedding; manual project/engine/query search/open-result/challenge state; global/project settings/TTL/concurrency/network/restart/limits; nonsensitive project/time/action/status audit. Responsive/readable/minimal build; destructive actions explain consequences and confirm.

## macOS operations

venv/pinned-or-constrained dependencies/playwright install chromium/controlled startup migrations. install_macos.sh/start.sh/stop.sh/doctor.sh and user LaunchAgent compatible with headed GUI; never claim a sessionless LaunchDaemon opens visible Chrome. Dedicated data directory (original example ~/Library/Application Support/HomeBrowserGateway/), separated SQLite/profiles/artifacts/logs/private config. Document logged-in session/awake Mac/network/energy; no aggressive pmset changes without authorization. Manual Serve→loopback destination/HTTPS/ACL and no-public-exposure verification; admin always authenticated. Safe manual stopped-browser backup/restore preserving permissions/secrets. README/.env.example without real secrets/SECURITY/endpoints/troubleshooting.

## Delivery stages and acceptance

Solid MVP then logical commits/extensions: (1) secure DB/admin/project/key/auth foundation; (2) persistent parallel browser manager/tabs/jobs/lifecycle/retention; (3) REST/ticket WS/actions/extraction/screenshots/budgets; (4) adapters/normalization/auto/challenges; (5) UI/macOS/audit/hardening/tests. Routine noncritical choices need no extra approval; document assumptions. Test/fix after each phase. If third-party live testing is blocked, supply fixtures and state the limitation; never simulate an unverified real success.

Acceptance requires reproducible installation/no subscription/default password, protected admin, ProjectX/project-b simultaneous isolated browsers/cookies, separate scoped keys/cross-resource/WS denial, unusable revoked/expired keys and one-time secret/no plaintext storage, documented navigation/rendered extraction/screenshots/errors, live DDG when available plus Google/Brave fixtures/honest failures, simulated human wait/resume without solver, TTL-preserved cookies/soft profile/hard correct-project double confirmation, default loopback/no public CDP/private+redirect denial, pytest/security/lint/operations/executed reports.

Final delivery report gives actual file paths/installation-test-start commands/verified functionality/results/real limitations. Never promise Cloudflare resolution or engine availability.
