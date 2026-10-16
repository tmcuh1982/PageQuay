# macOS operations and private access

[Français](OPERATIONS.md) | [English](OPERATIONS.en.md)

## Startup and diagnostics

From the repository root: `./scripts/start.sh`; foreground shutdown: Ctrl-C. `./scripts/doctor.sh` checks environment, installed browser, schema, administrator and Serve state when Tailscale CLI is present. It creates the data directory/applies migrations if needed but starts no browser.

Visible mode requires a logged-in graphical macOS user session; a system LaunchDaemon does not replace it. Availability depends on sleep, networking and the session. Configure energy in System Settings as needed; PageQuay does not change pmset. Already authorized remote desktop may support human intervention; PQ installs no remote access.

## Minimized windows

**Minimiser / Restaurer** in Projets / Profils and Sessions / Onglets minimizes/restores running headed browsers. Navigation/extraction continue; new tabs preserve state. Screenshots briefly restore for macOS rendering, then minimize again even after failure.

**Démarrer les fenêtres minimisées** sets global browser_start_minimized=true. Save and restart browsers; per-project JSON overrides may enable/disable it. Default off, ignored in headless mode. Restore before human checks.

## User LaunchAgent

Adapt `scripts/local.pagequay.gateway.plist.example` with absolute repository/data paths, without tilde or shell variables. Create logs/ with 0700 and output files 0600. Validate using plutil -lint, then copy to ~/Library/LaunchAgents/local.pagequay.gateway.plist:

```sh
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/local.pagequay.gateway.plist"
launchctl print "gui/$(id -u)/local.pagequay.gateway"
curl --fail http://127.0.0.1:8765/health/live
```

Unload using `./scripts/stop.sh` (launchctl bootout). The plist remains; delete it only to prevent future login loading. Bootstrap to reload. Never run foreground and LaunchAgent instances on the same profiles.

The plist specifies Aqua; reboot/login behavior must be validated on the target. If macOS denies Documents access, use a runtime copy elsewhere with Python imports that do not point back into Documents.

On the historical development Mac mini, the explicitly installed agent runs `~/Library/Application Support/PageQuayService/.venv/bin/python -m pagequay.cli serve`, working directory PageQuayService, with RunAtLoad/KeepAlive. Runtime sources/.env are copied from the checkout: updates must be deployed to that copy before restart. Data remains separately under ~/Library/Application Support/PageQuay. Installation creates no admin password.

## Local administration and Tailscale Serve HTTPS

Install/connect Tailscale using its [official guide](https://tailscale.com/docs/features/tailscale-serve), enable tailnet HTTPS as needed, and restrict access to this Mac/HTTPS port using ACL/grants before Serve. Serve exposes within the tailnet; **do not enable public Funnel**.

Two loopback sockets share one process: admin 8765, API 8766. PQ_PORT/PQ_API_PORT must differ. The API port permits only /v1/, /health/live, /health/ready and /openapi.json. Admin login/mutations/assets are denied even with admin cookies/localhost Host. The check uses actual destination port, not client headers.

Configure the exact hostname:

```dotenv
PQ_ALLOWED_HOSTS=["127.0.0.1","localhost","mac-mini.your-tailnet.ts.net"]
PQ_ALLOWED_ORIGINS=["http://127.0.0.1:8765","http://localhost:8765"]
PQ_SECURE_COOKIES=false
PQ_PORT=8765
PQ_API_PORT=8766
```

Restart PQ, then explicitly run:

```sh
tailscale serve --bg http://127.0.0.1:8766
tailscale serve status
tailscale funnel status
```

Validate HTTPS/tailnet-only, no Funnel routes, correct loopback destination; an authorized tailnet device reaches readiness/authenticated API, while admin/login/mutations return 404. An ACL-denied device and an outside-tailnet device must fail. No router/NAT/UPnP ports need opening. tailscale serve reset removes this machine's Serve routes; inspect other hosted services first.

Open admin **on the Mac** at http://127.0.0.1:8765/admin. Local HTTP cookies use PQ_SECURE_COOKIES=false; remote API uses HTTPS Bearer, not cookies. Never proxy the admin port. X-Forwarded-For/Proto grants no privilege. These instructions are not proof of real-network validation: run the target-machine recipe. Same-host HTTPS checks in release 1.0.1 do not establish another-device/ACL validation.

### Local administrator and API ports

In **Paramètres → Accès local**, set **Port administrateur** and **Port API local** (1024–65535), save, then restart PageQuay. Tailscale is not required. Ports must be distinct and available on 127.0.0.1. Availability is checked but not reserved; a later conflict can still fail startup.

The current listener stays active until restart; the page shows saved/active values and pending restart. Foreground: Ctrl-C then start.sh. LaunchAgent: use shutdown/bootstrap above. Update local clients to http://127.0.0.1:PORT and Tailscale's API destination if used. Saving the active value again cancels a pending change. Admin stays denied on the API port.

Persistent local-api.json (0600) under PQ_DATA_DIR overrides PQ_PORT/PQ_API_PORT at startup and in pq doctor. To revert to .env, stop, remove the override file, then restart. Before first launch or when a bad API port prevents startup, use PQ_API_PORT and remove any override. PQ_PORT provides the initial admin port; existing loopback allowed origins follow the saved administrator port. Old files containing only api_port remain compatible.

The historical installation uses admin http://127.0.0.1:8767/admin/ and API http://127.0.0.1:8787. These are machine-specific values, not defaults. Local changes do not edit Serve routes; update that destination explicitly.

### External HTTPS port

**Paramètres → Accès externe → Port HTTPS externe** selects the client-visible port 1–65535, default 443. It is distinct from loopback PQ_API_PORT. Apply creates a private route to the API, verifies it, removes the old PageQuay route and verifies final state. No PQ/browser restart; --bg persists across Tailscale restart.

8443 is a convenient alternative, e.g. https://mac-mini.your-tailnet.ts.net:8443. 8080 can also serve HTTPS; protocol follows [Serve configuration](https://tailscale.com/docs/reference/tailscale-cli/serve), not port convention. Choose an available port allowed by tailnet rules. The setting is global and changes only when applied; 443 is omitted from URLs.

Requires Tailscale CLI available to PQ, tailnet login, Serve/HTTPS enabled and exact hostname in PQ_ALLOWED_HOSTS. Other settings remain usable when Tailscale is absent. The form requires local admin/CSRF and cannot be used through client keys/API port.

LaunchAgent PATH is minimal. PQ also checks /usr/local/bin and /opt/homebrew/bin wrappers before the application binary. On the validated Mac a wrapper is required: directly calling the application binary produces a startup error instead of JSON and disables the button with “État Tailscale illisible”.

Update clients and ACL/grants after changing the port; PQ does not edit access rules. Another service's port, shared routes, temporary Serve or Funnel on that port are rejected before mutation. The command never resets all Serve settings. On failure it attempts old-route restoration/new-route removal; failed recovery reports an incomplete change and asks to check tailscale serve status.

## Backup and restore

1. Drain/cancel jobs, stop PQ and verify Chromium windows are closed.
2. Copy the **entire data directory**, including SQLite and any WAL/SHM, profiles/artifacts, to private storage. macOS ditto preserves permissions. Keep .env separately and privately.
3. Treat backups as secrets; never publish them or copy a live Chrome profile.
4. Stop PQ and back up current data before restore. Restore to a private directory, check ownership/0700 and sensitive files/0600, set PQ_DATA_DIR and restart.
5. Verify login/projects/sessions. Sites can invalidate restored cookies; PQ does not guarantee validity.

Copied flock files have no active kernel lock after shutdown. Interrupted jobs are not replayed. Never delete Singleton* while Chromium uses the profile.

## Logs and troubleshooting

- Database audit is automatically purged; operator rotates LaunchAgent stdout/stderr after shutdown according to private retention. No destructive periodic task is installed.
- BROWSER_CRASHED: check playwright install chromium, GUI session, versions and directory permissions. Keep sandbox enabled; see [startup diagnostics](STARTUP_DIAGNOSTICS.en.md).
- CONFLICT: profile in use or active jobs; drain rather than deleting locks/profiles.
- NAVIGATION_BLOCKED: scheme/port/DNS/private IP/domain rules; blocked public-page subresources may be expected.
- UPSTREAM_CHANGED/UPSTREAM_UNAVAILABLE: engine layout/network/unrecognized page. Separate live diagnostics from fixtures; no anti-bot bypass.
- waiting_for_human: act on the Mac, resume or cancel. Waiting is bounded and detection imperfect.
- RATE_LIMITED: inspect scope/cause and known Retry-After/retry_at. Full capacity has no predictable deadline. Engine quota is 6 attempts/60 seconds per project/engine. Use a new Idempotency-Key for a failed continuation when can_resume_continuation=true. Space polling or use WS events. Default REST quota 60/key/minute includes polling.
- `lsof -nP -iTCP:8765 -sTCP:LISTEN` should show loopback only. Each browser also has a launch-selected nonzero loopback CDP port; never expose it. Check using `lsof -nP -a -p <BROWSER_PID> -iTCP -sTCP:LISTEN`. [Transport](BROWSER_TRANSPORT.en.md).

## Resource budgets

Set in .env and restart:

| Setting | Default | Range |
| --- | ---: | ---: |
| PQ_AUDIT_QUEUE_SIZE | 512 events | 16–4096 |
| PQ_AUDIT_EVENTS_PER_MINUTE | 2400 | 60–10000 |
| PQ_AUDIT_EVENTS_PER_PROJECT_MINUTE | 600 | 30–5000 |
| PQ_AUDIT_MAX_ROWS | 20000 | 100–100000 |
| PQ_AUDIT_MAX_BYTES | 64000000 bytes | 1000000–256000000 |

Older detail may be purged at capacity before day-based retention. Admin/key/project/profile/settings operations have a separate reserve: queue 64, 5000 rows, 16000000 bytes. Each JSON detail is capped at 65536 bytes. Network collection tracks at most 128 requests/tab and 32 simultaneous size tasks service-wide.

Writes batch about every 250 ms. Console waits off the server loop for visibility up to five seconds; writer failure may show older data. Audit alerts report omissions/write errors since startup and persistent capacity purge counts. Even the admin reserve may overflow; audit is not guaranteed exhaustive.

Histograms separately retain known API response totals, including 401/429, over 24 UTC buckets. Failed writes retry in bounded buckets. Above capacity (512 pending dimensions, 8192 persisted), project/key dimensions coalesce while endpoint totals remain; the UI reports it. Normalized routes are also bounded. Abrupt stop or persistent shutdown failure can lose pending counters. Migration 006 backfills available API events from the preceding 24 hours once before purge, without reconstructing deleted detail.

Byte limits measure logical retained content, not SQLite/index/WAL files. Freed pages are reused; physical file size may remain at its historic maximum. Physical shrinkage requires separate offline backed-up SQLite maintenance.

Page titles: 512 characters with title_truncated; challenges: 20000-character sample; links/metadata: bounded strings/collections. PQ_MAX_CONTENT_BYTES defaults to 2000000 and limits HTML/text, structured envelopes and job results/errors. Oversized reads fail 413; unavailable frames are reported. Oversized historical results are removed on access with explicit failure. Renderer/driver memory is not bounded by these settings.
