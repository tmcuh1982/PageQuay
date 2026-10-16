# SPEC_API — original reference contract (v1)

[Français](SPEC_API.md) | [English](SPEC_API.en.md)

Historical expected surface, with indicative paths. Delivered schema must be consistent/versioned/OpenAPI documented/tested. **Every client route requires authentication AND project authorization.** Admin requires Web session/CSRF or a strictly separate channel unavailable to client keys. The current authoritative contract is [OpenAPI](../openapi.json); this reference does not override later implementation choices.

## Web administration

GET /admin dashboard/login required; GET /admin/projects with create/edit/enable/stop forms; GET /admin/keys with create/one-time secret/revoke/rotate/scopes/expiry; GET /admin/settings global/project overrides/TTL/quotas; GET /admin/audit nonsensitive events; GET /admin/search manual per-project test.

## Project API

POST /v1/projects/{slug}/search returns 202/job_id, or documented immediate short-task variant:

```json
{"engine":"auto","strategy":"fallback","query":"agricultural robotics 2026","limit":10,"locale":"fr-FR"}
```

Illustrative final response, not a real search result:

```json
{"status":"completed","project":"projectx","query":"agricultural robotics 2026","results":[{"rank":1,"title":"Non-real example","url":"https://example.org/article","snippet":"Example content","source_engines":["duckduckgo"],"fetched_at":"2026-10-09T18:00:00Z"}]}
```

POST /v1/projects/{slug}/tabs creates an allowed-URL tab:

```json
{"url":"https://example.org","wait_until":"domcontentloaded"}
```

GET /tabs, GET /tabs/{tab_id}, DELETE /tabs/{tab_id}; POST /tabs/{tab_id}/navigate loads allowed HTTP(S), emitting completion WS event. Paths are relative to /v1/projects/{slug}.

POST /tabs/{tab_id}/actions validates browser:interact actions:

```json
{"actions":[{"type":"click","selector":"#details"},{"type":"wait_for_selector","selector":"article"}]}
```

GET /tabs/{tab_id}/content?format=text, html, links or metadata; GET /tabs/{tab_id}/screenshot requires screenshot:read and bounded size/frequency. Structured extraction and original images were added later; see current guides.

GET /jobs/{job_id} is project-only; states queued/running/waiting_for_human/completed/failed/cancelled. POST /jobs/{job_id}/cancel requires authorization. POST /ws-ticket with Bearer creates a short-lived, project-bound, minimal-permission one-use ticket. The original illustrative WS /events?ticket=<ephemeral-ticket> forbids API keys in URLs, requires safe logging/Origin checks/continuous authorization, and explicitly permits a safer initial-auth-message/subprotocol variant. **Delivered PageQuay uses the first message, not the query string.**

```json
{"event":"challenge.required","project":"projectx","job_id":"opaque-id","tab_id":"opaque-tab-id","at":"2026-10-09T18:00:00Z"}
```

GET /health/live exposes only minimal local state; GET /health/ready limits information and authenticates sensitive fields.

## Headers and errors

Authorization: Bearer <API_KEY>, never a query parameter.

```json
{"error":{"code":"FORBIDDEN","message":"Insufficient permission for this project","request_id":"opaque-id"}}
```

Standard codes: UNAUTHORIZED, FORBIDDEN, INVALID_INPUT, NOT_FOUND, RATE_LIMITED, NAVIGATION_BLOCKED, TIMEOUT, BROWSER_CRASHED, CHALLENGE_REQUIRED, CONFLICT, INTERNAL_ERROR. Job/artifact/tab/WS ticket/profile IDs are unguessable and linked server-side to project ownership; knowing another resource ID must not grant access.

## Future extensions outside MVP

Secure MCP exposing limited internal API tools, never public CDP; signed outgoing webhooks; additional adapters/shared result index without profile-secret mixing; advanced per-domain retention. Keep these outside the critical path until the foundation is tested.
