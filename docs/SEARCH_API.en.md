# PageQuay search — additive 0.2.0 contract

[Français](SEARCH_API.md) | [English](SEARCH_API.en.md)

Optional request/response fields extend /v1 without changing job paths/states. GET /openapi.json serves client/health schema on the API port (default 8766) and private HTTPS, without admin routes/secrets. [Committed schema](openapi.json).

## Limits and accounting

| Guard | Scope/window | Counted operations |
| --- | --- | --- |
| Search.limit 1–50, default 10 | Request validation | Requested maximum, not page aggregation |
| search_max_results default 10 | Global/project configuration | min(limit, search_max_results) returned per job |
| DuckDuckGo HTML adapter | Before 0.2: initial document only | Asking for 50 never itself requested 50 from the engine |
| PageQuay engine quota 6/60 seconds | Project + engine, shared by keys/admin | Every search page attempt, including native continuation, failed attempt and CAPTCHA |
| REST quota, default 60/60 seconds | API key, minimum key/project per_key_rate_limit | Authorized creation/replay/poll/control/download/key-info; auth/scope checked first |
| Job capacity | Global/project, default 30 queued/active | New admission, no known time window |
| Browser/tab capacity | Default 3 global browsers, 8 tabs/project | Browser start/tab allocation; at most one owned search tab |

Fixed quota windows start on the first admitted call and persist in SQLite. They are not rolling windows or DuckDuckGo quotas. Stored remainder uses REST quota, no new engine attempt/tab. Redirects/resources/resuming the same CAPTCHA are not new engine attempts. Other limits remain: screenshots 6/60 seconds/key, WS messages min(key quota,60)/60 seconds and bounded connections.

Historical 5/10/10/10 output for requested 5/10/20/50 is explained by PQ's cap of 10. Six successes followed by four RATE_LIMITED outcomes are consistent with the project/engine guard, but old responses cannot prove every failure's cause. No exact upstream quota is inferred. The inspected reference project had search_max_results=10 without override.

## First slice and continuation

Requests contain query (1–500 characters), engine, limit (1–50), locale (default fr-FR). Multiple keywords form one query string; distinct searches need separate operations/cursors/idempotency keys. No implicit batching.

### Country/region and recency

DuckDuckGo accepts optional region and time_range, also available in console Recherche after selecting DuckDuckGo:

| Field | Values | Default |
| --- | --- | --- |
| region | DuckDuckGo codes such as fr-fr, pl-pl, us-en, uk-en, wt-wt | null, derived from locale |
| time_range | any, day, week, month, year | any |

```json
{"query":"robot agriculture","engine":"duckduckgo","region":"fr-fr","time_range":"week","limit":10}
```

Region overrides the locale-derived market without changing locale; it combines region/language according to [DuckDuckGo's list](https://duckduckgo.com/duckduckgo-help-pages/settings/params), without guaranteeing country-only sites. Unknown explicit codes return 422. Legacy locales remain accepted/transmitted; the engine may ignore combinations.

Time range uses df values d/w/m/y or empty, following the HTML adapter mapping. Every native load sends region/time explicitly rather than relying on profile history. Engine tokens/offsets stay native, never invented. An explicit region or non-any time range requires effective DuckDuckGo; auto/Brave/Google return 422 before admission. If engine is omitted, project configuration must choose DuckDuckGo.

Responses/partials echo locale/region/time_range. Preserve them across continuation; changing them invalidates the cursor. They participate in idempotency. Omitted filters and region=null,time_range=any are equivalent, including older idempotency records. SQLite migration preserves unfiltered cursors.

**Freshness:** fetched_at is PQ collection time, not publication or event time. New/updated pages may describe old events. Inspect publication/update/event dates separately and retain uncertainty if absent; filters do not validate those dates.

limit remains a per-operation maximum capped by project policy, neither a page count nor a fill guarantee. A call loads at most one native page; excess results are stored and delivered before another page is loaded.

```http
POST /v1/projects/projectx/search
Authorization: Bearer <key>
Content-Type: application/json
Idempotency-Key: projectx-run-123-query-1-slice-1

{"query":"robot agriculture","engine":"duckduckgo","limit":10,"locale":"fr-FR"}
```

Admission:

```json
{"job_id":"JOB_ID","status":"queued","url":"/v1/projects/projectx/jobs/JOB_ID","idempotency_replayed":false}
```

Poll relative url using the same Bearer. Completed result preserves project/query/results/engine_errors and adds:

| Field | Meaning |
| --- | --- |
| engine, engines_used | Actual engine(s), mixed for merge; empty failures may retain requested engine |
| requested_count, effective_limit, returned_count | Requested, capped, actually returned |
| next_cursor | Opaque 43-character token or null |
| has_more | true: remainder/native form; false: detected end/imposed stop; null: unknown/unusable continuation |
| cursor_expires_at | Proposed cursor Unix UTC expiry, otherwise null |
| pages_fetched | Cumulative engine documents, not slices |
| duplicates_discarded | Cumulative normalized-URL duplicates |
| stop_reason, partial | Slice stop and known incomplete outcome |

Resume using the actual cursor, same project/query/engine/locale/region/time_range and a **new** Idempotency-Key; limit may change:

```json
{"query":"robot agriculture","engine":"duckduckgo","limit":10,"locale":"fr-FR","cursor":"REPLACE_WITH_ACTUAL_43_CHARACTER_CURSOR"}
```

Stop when next_cursor=null and inspect has_more/stop_reason; never treat a repeated first page as the next one. Each result retains normalized url; exact_url preserves the unwrapped target's parameters/encoding/fragment. Deduplication never rewrites exact_url. rank is chain-wide; engine_rank is organic order within page_number. source_engines/fetched_at record provenance. Merge preserves the first exact URL and combines provenance.

Explicit duckduckgo never switches engines. auto permits configured fallback/merge, reports provenance/errors and offers no cursor. Ask explicitly for DuckDuckGo for verifiable pagination. Locale uses native kl mappings (fr-fr/us-en/pl-pl/uk-en); accepted PQ locales are not guaranteed supported or ranking-stable upstream.

## Native pagination and bounds

Only a Next form actually present in DuckDuckGo HTML is followed, with its HTTPS /html/ action, GET/POST method and hidden fields. No fabricated page number, offset or vqd token. Chromium uses the project profile and guarded proxy; the API key never goes to the engine.

SQLite stores remainder/native state; the client gets a random token. Repeated pages with no new URLs or already-used forms stop progress. Partial duplicates are removed; absent recognized Next means unknown end, not proven exhaustion.

| Setting | Default | Range |
| --- | ---: | ---: |
| search_max_results per slice | 10 | 1–50 |
| search_max_pages per chain | 10 | 1–30 |
| search_max_total_results unique/chain | 200 | 1–1000 |
| search_cursor_ttl_minutes | 15 | 1–60 |
| search_max_cursors_per_project active states | 100 | 1–1000 |

Document max_content_bytes defaults to 2 MB; parser at most 200 results/document, title 500 chars, snippet 2000. Form max 40 fields/16 KiB. Total operation budget job_timeout_seconds + human_timeout_seconds (default 180+120); navigation default 30 seconds, shared human deadline up to 120 seconds per job. Server does not wait for quotas. job.progress emits fetching_search_page. Each call returns at most one native page or remainder.

stop_reason values: result_limit, page_complete, exhausted, continuation_unavailable, continuation_unusable, repeated_page, repeated_continuation, no_progress, page_limit, total_results_limit, cursor_capacity, cursor_expired, pagination_not_supported. Failures may use lowercase codes such as rate_limited/timeout. Known limits/repetitions set partial=true; a normal slice with continuation is not a partial failure.

## Cursor lifetime and invalidation

- Expiry is absolute from first load; resume does not extend it. Expiration returns 410 CURSOR_EXPIRED, or that job error if expiry occurs in queue.
- Binding covers project, validated query, DuckDuckGo, locale, region and time range; changes return 409 INVALID_CURSOR before job creation. Another same-project search:read key can continue it.
- Reservation/job creation are atomic. Without idempotent replay, reserved/consumed reuse returns 409 CURSOR_USED with existing job path.
- Failure/cancellation releases reservation; an unexpired cursor can be tried in a new operation. Quota errors expose resumability. Restart fails interrupted jobs/releases reservations while unexpired SQLite state survives.
- Profile reset invalidates cursors; content purge deletes state/cursors. Ordinary browser restart preserves both, though native upstream parameters may expire independently.
- Consumed state is erased after success; inactive expired states at maintenance (30 seconds), traces one day after expiry. Job results follow content TTL.

## HTTP and asynchronous limits

429 retains the error envelope with details and Retry-After when known. Capacity release cannot be predicted, so timing stays null.

```json
{"error":{"code":"RATE_LIMITED","message":"PageQuay request quota exhausted; retry after the window resets","details":{"scope":"project_engine","cause":"pagequay_quota","engine":"duckduckgo","limit":6,"window_seconds":60,"retry_after_seconds":24,"retry_at":1791655220,"can_resume_continuation":true,"resume_cursor":"ACTUAL_CURSOR","partial_results":[]}}}
```

Other scopes: api_key, job_queue, browser_capacity, project_tabs, upstream_engine. Upstream 429 yields cause=upstream_http_429 and usable Retry-After; throttling HTML yields upstream_throttling without inferred quota. Unknown cause remains unknown. Already collected results/provenance remain in job.result and rate-limit details.partial_results. Merge can fail after one successful engine while retaining inspectable partials.

CAPTCHA enters waiting_for_human until manual resume/cancel/timeout. Timeout yields TIMEOUT, not proof of an upstream quota. After manual action, POST job path + /resume. No solver, verification click or identity switch.

## POST /search idempotency

Optional but recommended Idempotency-Key: 1–128 ASCII characters in [A-Za-z0-9._:-], scoped to project + API key + POST /search. Bodies compare after validation/defaults; omission/null equivalence and query/locale normalization are preserved.

Same key/body returns the same job/current state/path with idempotency_replayed=true for 24 hours. Different body: 409 CONFLICT. SQLite check/reservation/write has no await; concurrent single-process calls converge. Jobs/associations survive restart without automatic replay. Invalid/revoked/expired or unauthorized keys remain denied before replay.

Replay consumes REST quota, not a new job/engine attempt. After 24 hours reuse may create a new operation. Result TTL (default 60 minutes) is independent: finding a job does not restore purged results. Replaying a failed job keeps it failed; retry after quota with a new key/cursor only when can_resume_continuation=true. Persist key/body before sending; after uncertain receipt resend exactly the same request/key until receipt is established.

## Lifecycle and ProjectX example

Each search owns one internal tab, closed after success/error/cancel/human timeout, without affecting others. It stays available during human wait. Cursors retain no tab; stored remainder opens none.

[search_duckduckgo.py](../examples/search_duckduckgo.py) is a standard-library server client: iterates queries/jobs/continuations and stops on explicit/unknown end, CAPTCHA, error or local limit. Private 0600 checkpoints are saved before creation and after receipt. Known-quota retries are bounded; CAPTCHA intervention is separate.

```sh
# Supply PQ_API_KEY through the server environment/secret manager.
python3 examples/search_duckduckgo.py \
  --url https://YOUR-PQ-HOST --project projectx \
  --query 'robot agriculture' --query 'robot irrigation' \
  --locale fr-FR --region fr-fr --time-range week --limit 10 --max-slices 3 \
  --checkpoint /private/path/projectx-ddg.json
```

Rerun with same checkpoint/arguments for uncertain receipt. After manual resume, the checkpoint reads the result. Slices can be remainder; pages_fetched proves native progression. Bearer is absent from source/checkpoint/results/URLs/cursors/frontend. API transport redirects are denied.

## Evidence and limitations

Simulation covers three progressive pages, remainder, duplicates/repetition, deadlines, binding, bounds/shared quotas, concurrent idempotency/SQLite reopen, cancellation/timeouts/CAPTCHA/cleanup. Real Chromium fixtures test native POST, repeated/Unicode fields and proxy transport.

Bounded live attempts for “robot agriculture” (fr-FR), “agricultural robotics manufacturers” (en-US), “robots agricoles France” (fr-FR) all encountered DuckDuckGo CAPTCHA, challenge.required, five-second test human expiry and confirmed tab cleanup. **No real result page was obtained; three-page live pagination remains unvalidated.** Raw local HTML/reports are excluded from Git. Passing a diagnostic means outcome recording, not engine acceptance. [Test report](testing/REPORT.en.md).
