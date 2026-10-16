# PageQuay security

[Français](SECURITY.md) | [English](SECURITY.en.md)

## Scope and invariants

Private application for an operator and known clients. Web pages are untrusted; API keys and profiles are secrets. Every resource is linked server-side to a project with a random ID. Slugs never become filesystem paths. No default administrator, client-key administration API, public CDP or client-supplied code execution.

Server sessions use random 256-bit tokens, stored as SHA-256 hashes in SQLite, with 12-hour absolute and 30-minute idle lifetimes. Login creates a new session and invalidates the previous one; logout and all UI mutations require CSRF protection. Cookies are HttpOnly, SameSite Strict and Secure when configured for HTTPS. Login also has CSRF protection and five attempts per transport/five minutes plus a global limit. Passwords use Argon2id and require at least 14 characters. Errors do not echo invalid form values.

API keys use 256-bit CSPRNG secrets, SHA-256 hashes and constant-time comparison after lookup. Each has one project and explicit scopes. Fast hashes are appropriate for high-entropy random keys; human passwords use slow Argon2id. The nonsecret prefix identifies a key; its full secret is shown once. Expiry/revocation are rechecked for requests, active jobs and WebSockets. Only a local admin session with CSRF can edit a key: project/secret and quota counter are preserved, revoked keys cannot be reactivated, expiry must be future or absent, and at least one recognized scope and bounded quota are required. Removing a permission cancels dependent jobs. Audit `key.updated` never contains the secret.

## Local browser control

The child browser uses an explicit nonzero CDP port on `127.0.0.1`. The relay preserves Playwright initialization and validates the address, port and endpoint path advertised by its own child; it does not discover existing browsers. The Playwright pipe ends at the relay. EOF, cancellation, timeout and transport failure clean up the child.

This adds no public route or arbitrary API command. The CDP port has no authentication: local processes that can access it are within the operator's trust boundary. Never expose it through proxy, tunnel or Tailscale Serve. Web pages remain subject to the proxy and loopback denial. [Transport](docs/BROWSER_TRANSPORT.en.md).

## Browser egress

Each profile has a loopback proxy on an ephemeral port. It validates URL, scheme and port, checks **all** DNS answers, then connects directly to a validated literal IP. Chromium verifies TLS inside CONNECT. Playwright also intercepts subrequests; the proxy remains the connection control if redirects escape interception. Denied: loopback, private, link-local, tailnet CGNAT, multicast, reserved, IPv6 mapped/6to4/Teredo/standard NAT64, cloud metadata and ambiguous IP literals. Public ports are limited to 80/443. Allowlist matches are exact; blocklists include subdomains.

`chromium_sandbox=True` explicitly enables the sandbox that Playwright otherwise disables by default ([reference](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-option-chromium-sandbox)). QUIC and unproxied UDP WebRTC are disabled; remote WebSockets and Service Workers are blocked. Native Chromium `socks=` proxy routing points ws/wss at a second loopback listener, using an explicit HTTP proxy URI. It rejects before DNS/upstream connection, preserves the native JavaScript constructor and has no DIRECT fallback. Frames, popups and workers are covered; stopping the listener does not restore direct access. PageQuay's command WebSocket is unaffected.

Camera, microphone, location and clipboard permissions are not granted. Ordinary downloads are cancelled; uploads and arbitrary file access are not exposed. Dialogs are dismissed without validating challenges. The explicit [download_image](docs/DOWNLOAD_IMAGE.en.md) API separately reads bounded, validated original image bytes through the guarded browser; it does not enable ordinary browser downloads.

This is **not an OS firewall**. A compromised browser, manually added extension, authorized local process or manual profile modification is outside the model. CONNECT does not decrypt HTTP within TLS or independently guarantee URL-level policy. Origin filtering, Playwright and validated connection IPs work together. Full confinement requires administered OS network controls. No production LAN exception exists; test exceptions are injected only in their Python process.

## Administration, storage and content

CLI listeners bind only `127.0.0.1`: admin 8765 and API 8766 by default, with configurable distinct ports. Local API port changes do not require external access. Actual socket destination limits the API listener to `/v1/`, both health routes and `/openapi.json`, for HTTP/WebSocket; Host, proxy headers or admin cookies cannot bypass it. The application rejects non-loopback transport and uses explicit Host/Origin settings. Remote access is Tailscale Serve HTTPS to **the API port only**, protected by tailnet identity/ACL and then the API key. Never proxy the admin port; do not enable Funnel. Local CSP, anti-framing, nosniff, no-store, referrer policy and limits on responses/queues/tabs/browsers/actions/rates/artifacts apply.

Jinja escapes templates; external content uses `textContent`, not `innerHTML`. Extracted HTML is an attachment with sandbox CSP. Screenshots require an admin session or project scope. Remote pages are never embedded in admin iframes. Content passed to an LLM remains untrusted data; do not follow instructions within it.

Directories are 0700; SQLite, artifacts and locks are 0600; CLI umask is 077. Profiles are readable by the macOS user and contain plaintext cookies/secrets; the application promises no encryption at rest. FileVault is a separate macOS control. Per-profile flock locks are released by the kernel after a crash. Reset is manual, requires two confirmations and a short-lived session-bound intent, and is refused with queued/active jobs. Back up only after complete shutdown.

Audit retains action, time, actor/project/job/tab IDs, function, navigation/resource/destination URLs, HTTP status and encoded response-body size when available. URL queries/fragments are intentionally retained verbatim; only userinfo credentials are removed. URLs may therefore contain private data or site tokens. Pagination labels use fixed recognized values, not arbitrary button text, selectors or form values. Authorization/Cookie headers, POST bodies, page HTML and screenshots are not logged; values in URL queries/fragments remain present. Errors retain controlled codes, not raw browser messages. Viewing is local-admin-only, with retention and Jinja escaping. Uvicorn access logs are disabled. LaunchAgent file rotation is the operator's responsibility; see [operations](docs/OPERATIONS.en.md). Inspect what Playwright DEBUG/tracing records before enabling it on real sessions.

Titles, challenges, HTML/text/links/metadata/structured DOM are read in an isolated Chromium world, with limits before return. Titles are capped at 512 characters and flag truncation; oversized content fails with 413. Frame resolution does not fetch full frame trees or target titles. Job results/errors, including partials and oversized historical records, are bounded before persistence.

Audit has bounded admission queues, global/project quotas, logical byte/row caps and a separate admin reserve. Pending requests and size-collection tasks are bounded. A dedicated worker owns a SQLite connection and batches commits; the event loop does not wait on it. API totals are coalesced separately from detail, and alerts show saturation/coalescing/write failures. These caps guarantee neither complete audit retention nor immediate SQLite shrinkage. Abrupt shutdown can lose recent uncommitted data. Chromium/Playwright memory is not globally bounded; use OS confinement when required.

## Verification and reporting

See [test evidence](docs/testing/REPORT.en.md). Fixtures validate known layouts, not engine availability. Crash tests deliberately close a context and do not reproduce every OS failure. Validate Tailscale ACL, login-time LaunchAgent and full restore on the target machine.

Report reproducible steps and nonsensitive correlation IDs. Never attach a browser profile, API key, raw authenticated page or secret-bearing screenshot to a public issue.

## User responsibility

Users are responsible for their use, modification and deployment of the source code, subject to applicable law. See [the disclaimer of liability](README.en.md#use-and-disclaimer-of-liability), including responsibilities concerning third-party content and services.
