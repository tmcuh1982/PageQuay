# PageQuay status — October 16, 2026

[Français](STATUS.md) | [English](STATUS.en.md)

Public version **1.1.0**, published as [v1.1.0](https://github.com/tmcuh1982/PageQuay/releases/tag/v1.1.0), source commit 11ce7dd. Wheel, sdist and SHA256SUMS were downloaded after publication and matched the built files. Publication did not deploy/restart the installed service. Deployment/other-device Google/Tailscale ACL/full restore validation remain separate from source release status.

## Delivered features

- French local administration, isolated persistent Chromium profiles/projects, admin sessions and scoped project API keys. Documentation in French and English; the console's UI remains French.
- Separate configurable local admin/API ports and global external HTTPS port through private Tailscale Serve. Active/pending local settings are distinct; local changes require restart, external Serve changes are immediate.
- Key security edits preserve secret/project; permissions, quota, expiry and name are editable. Calling-key info exposes scopes, expiry, configured/effective quota and current window balance.
- REST/WebSocket, bounded async jobs, navigation/actions, screenshots and protected temporary artifacts.
- Google/DuckDuckGo/Brave adapters; manual challenge waiting/resume. DuckDuckGo native continuations, detailed quotas, POST idempotency, internal-tab cleanup and ProjectX client; persistent region/time filters.
- Minimize/restore and start-minimized option; new tabs preserve minimization.
- Rendered DOM text/HTML/links/metadata/structured JSON with optional filtered tree, open Shadow DOM and bounded iframe documents with partial indicators. Dimensioned aria-hidden frames are omitted without consuming content slots.
- Guarded original JPEG/PNG/WebP acquisition, exact final URL, bounded bytes/deadline, SHA-256 and private binary artifact.
- DNS/IP-validating proxy, private-destination denial, native page-WebSocket denial, quotas/retention and explicitly confirmed manual reset.

See [OpenAPI](openapi.json), [search](SEARCH_API.en.md), [extraction](EXTRACTION.en.md), [images](DOWNLOAD_IMAGE.en.md), [architecture](ARCHITECTURE.en.md).

## Latest validation

| Check | Observed result |
| --- | --- |
| 1.1.0 general suite | 292 passed, 96 skipped; existing Starlette/httpx deprecation |
| Targeted real Chromium | 72 passed: images/client/acquisition/challenges/native WS/hidden frames |
| Ruff/format/lock/diff | Modified Python files conform; locked offline sync and diff check pass |
| Binary release files | Built from committed sources; three published files match locally built hashes |
| Live image recipe, October 15 | Disposable service: original UBTECH JPEG, 689381 bytes, verified SHA-256; not installed-client deployment proof |

Counts from overlapping/historical suites must not be added. Fixture success does not establish engine availability. Virtualized pages need explicit actions; closed Shadow DOM/unexposed JS/pixel-only data are not ordinary DOM exports. No automatic CAPTCHA solving.

## Historical publication/deployment record

The first complete push advanced main from 5e85c7b to ad0c861 without rewriting history. GitHub CLI was used after the app connector's 403; credentials remain outside the repository. Public source publication does not expose the service/profiles. Private captures, raw diagnostics, environments, databases and keys remain ignored; only reviewed evidence/fixture JSON is tracked.

Early 0.2 delivery included window control, admin/API separation, key editing and DuckDuckGo continuations; region/time filtering was additive with migration 004. No live filtered-search success was claimed. Later delivery records:

- KUKA 0.2.1 reproduced/fixed WORLD_NOT_FOUND using isolated native frame slots and owning CDP targets. Real final URL exact, 69 main blocks, f1 extracted, partial=false/truncated=false; player had no mounted text. Historical 249 passed/4 skipped, then 33 targeted after final inventory adjustment. Installed source/package/schema verified; private UniversRobot-key recipe remained separate.
- Navigation 0.2.2 separated redirects/challenges/scope, retained strict subframe denial and added public OpenAPI equality regression. Historical 265 passed/4 skipped plus overlapping final subsets. No real CAPTCHA solving; service keys/projects/settings preserved.
- AgXeed/OnRobot fixes handle stale CDP candidates, title coherence, CAPTCHA widgets, URL/title budget reservation and exact shadow-frame target roots. [AgXeed read](AGXEED_READ_FIX.en.md), [export](AGXEED_EXPORT_FIX.en.md), [CAPTCHA](CAPTCHA_WIDGET_FIX.en.md), [OnRobot](ONROBOT_FRAME_FIX.en.md).
- Browser transport 0.2.4 / v1.0.0 preserved native WebSocket while denying ws/wss before DNS. Base suite 343 passed/4 skipped; v1 metadata contract six passed. Music Store searches/product navigations returned HTTP 200 in fresh Chrome/Chromium and one retained Chromium session; first Fender click timed out. This is site/session evidence, not guaranteed future challenge-free access. Service metadata remained 0.2.2 at that historical stage.
- 1.0.1 made admin/API ports separately configurable. General suite 276 passed/74 skipped; same-host installed login/API/Tailscale checks passed, without new other-device validation. [Notes](releases/1.0.1.en.md).

Historical tests and remaining recipes are in [the report](testing/REPORT.en.md). Machine backups/logs mentioned in historical notes are private evidence paths, not shipped files or current endpoint guarantees. For future changes, [publish and verify](PUBLISHING.en.md) the remote commit/content before claiming synchronization.
