# Home Browser Gateway — original Codex instructions

[Français](README.md) | [English](README.en.md)

This directory preserves the **original implementation brief**, not the current program/manual. Original product name HBG was later changed to PageQuay. For delivered behavior, use [the current README](../../README.en.md), [status](../STATUS.en.md) and [OpenAPI](../openapi.json); requirements below are not evidence that every item was implemented/tested.

## Original usage

1. Extract the original archive into a new empty Git repository.
2. Open that directory in Codex.
3. Send [PROMPT_CODEX](PROMPT_CODEX.en.md) as the main implementation instruction.
4. Keep [SPEC_API](SPEC_API.en.md) and [acceptance checklist](RECETTE.en.md) beside it.
5. Review generated tests/docs before any network exposure, including private networks.

## Intended result

Free self-hosted Mac mini service: one project per isolated persistent Chromium/Chrome profile, concurrent sessions, browser-based Google/Brave/DuckDuckGo search, REST/WebSocket navigation/extraction/tabs/progress, lightweight admin for project/key/scope/expiry/revocation/activity/settings, distinct content-cache/browser-close/soft-restart/hard-reset policies, auth/quotas/audit/SSRF controls and private Tailscale Serve without router ports.

Dedicated automated profiles must never reuse personal Chrome profiles. Human challenges must be reported and manually resolved, never bypassed. Engine layouts/limits change; report failures honestly. Sites partly control cookie lifetime; soft restart does not guarantee remote login validity. Clearly distinguish executed macOS tests from pending target-machine validation.

Original instructions are French; English companions provide access to the same reference requirements. Code identifiers/endpoints/comments should be professional and consistent, preferably English. References: [Playwright](https://playwright.dev/python/docs/api/class-browsertype), [Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve), [FastAPI](https://fastapi.tiangolo.com/).
