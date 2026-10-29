# Structured JSON extraction

[Français](EXTRACTION.md) | [English](EXTRACTION.en.md)

On an already navigated tab, with the project's `content:read` key:

```http
GET /v1/projects/{slug}/tabs/{tab_id}/content?format=structured
Authorization: Bearer <key>
```

The 202 response gives the job ID/URL. Poll until completed, then download `result.url` with the same key; the artifact is `application/json`. Normal job errors/challenges apply. Add `&include_dom=true` for the filtered DOM tree. Default is false; true with another format returns `INVALID_INPUT` (400); unknown formats return 422. Existing text/html/links/metadata contracts are preserved. [Acquisition](ACQUISITION.en.md) documents evidence, expected URLs, XPath and typed frame failures.

## Schema version 1.0

| Field | Contents |
| --- | --- |
| schema_version, source | 1.0, rendered_dom |
| url, title, metadata | Current URL, title, language, canonical, description, meta list and parsed JSON-LD |
| blocks | DOM-ordered heading, paragraph, list, code, quote, table and frame blocks |
| content_root | First visible main ID, otherwise body; reading blocks come from this region |
| links, images | Document-wide collections, absolute links and alternative text |
| tables | HTML/ARIA table/grid/treegrid, captions, rows/cells, headers and spans |
| controls, forms | Types/names/labels/text options, disabled/required and form associations; no current/initial input/textarea values |
| landmarks, visuals | Page regions; canvas/SVG flagged for screenshot interpretation |
| frame_id, frames | Main f0 and child documents with ID, parent, URL, name, extracted/omitted/unavailable status |
| stats | Visited/included nodes, open shadow roots, copied characters |
| truncated, truncation_reasons, frame_limit_reached, partial | Encountered limits/malformed elements; unavailable children also set partial |
| dom, optional | node_id/tag/attributes/children; text nodes, #shadow-root and projected slot content |

IDs n1/n2/etc. are local to a document and snapshot; include frame_id for a full reference. They are not action selectors and may change after extraction/mutation. Table blocks refer to table_id; forms contain control_ids. List items have `{node_id,text,children}` with nested lists in children. The tree uses an attribute allowlist and is not complete HTML.

Real local fixture outputs: [compact JSON](testing/structured-complex-compact.json), [with DOM](testing/structured-complex.json). Localhost URLs are ephemeral test addresses.

## Why rendered DOM

Initial HTML misses JavaScript-created content. PQ's existing page.content() already serializes the rendered main document, but does not expand open Shadow DOM or iframe documents. In the fixture, parsed HTML contains hydrated text but misses the shadow heading and iframe text; structured JSON includes all three.

Playwright can read individual authorized frames, including other origins. Open shadow roots/slots are traversed using actual projected nodes; closed roots are not available through shadowRoot. The optional response tree helps relate components/ARIA regions/blocks to nodes; compact blocks/tables do not require it. On the fixture, unindented Python serialization grows from 5593 to 12390 bytes with DOM. No Trafilatura/Extruct dependency is added: the goal is rendered structure, not just article text.

## Limits

- At most eight visible document reads including main; inventory at most 32 frames. Hidden frames are reported without consuming read slots, including dimensioned `aria-hidden="true"` frames since 1.1.0. Excess inventory/visible reads set frame_limit_reached/partial. Global budget 40 seconds, per-frame 10 seconds; global overrun is TIMEOUT. Detached/unresponsive frames stay unavailable.
- Per document: 8000 visited nodes including omitted/hidden nodes; counted depth 32 with at most eight neutral envelopes discounted per path (absolute physical depth 40, body at 0); text budget min(160000, max_content_bytes/8). URL/title reserve budget before metadata/DOM. Maximum 400 blocks, 300 links, 100 images/controls, 300 text options per select, 20 tables, 50 rows, 30 cells/row, 30 forms. JSON-LD visits at most 10 scripts including invalid ones, 20000 characters/script and bounded objects/depth/collections; parsed, never executed.
- Credit applies only to `div`, `span`, and `picture` elements whose attributes are restricted to `id`, `class`, `style`, and `data-*` (at most 32 attributes). Editable elements, open Shadow hosts, and slot-assigned elements are excluded. Roles, ARIA attributes, labels, language or interaction attributes therefore prevent credit. Each branch inherits credit already consumed on its path; siblings do not share a global counter. Envelopes remain in the filtered DOM and consume the usual node and text budgets. Text, images, links, headings, lists, tables, controls, Shadow roots, and slots receive no credit. Every depth cut retains `depth`, `truncated`, and `partial`. XPath provenance keeps its independent 32-segment bound: recovered content may have `xpath=null`, `xpath_reason=depth_limit` without content omission.
- On structured-module load, the local `pagequay.extraction` log records `structured_reader_loaded` with version, schema, and `script_sha256`, the SHA-256 fingerprint of the script actually loaded into `SCRIPT`. This fixed diagnostic contains no URL or page data and does not reread the file during extraction.
- Limits are flagged; max_content_bytes, disk quota and TTL also apply. Oversized final representations are rejected by artifact controls.
- Only currently mounted content is captured. Explicitly wait for SPA hydration, scroll/click virtualized/lazy content and extract again. No automatic infinite scroll/click/loading.
- CSS visibility filtering is heuristic: display/visibility/content-visibility, hidden, aria-hidden. It does not reconstruct geometry, occlusion, pseudo-elements or exact rendering. Frame snapshots are sequential, not atomic.
- Closed shadow DOM is not traversed. Known iframe documents can be captured separately under a closed host only when identity is verifiable. Unexposed JavaScript state is not recovered. Canvas pixels/SVG charts are not converted to data: use screenshots or accessible text. No OCR is added.
- No cookies, storage, script/style, input/textarea values or option value attributes are included. Project/scope protection remains; no CAPTCHA solving.

## Validation

```sh
.venv/bin/pytest tests/test_structured.py tests/test_openapi.py --browser --headed -q
```

Fixtures cover hydration, open shadow/slot, closed root, cross-origin iframe on another local port, hidden frame, nested lists, HTML/ARIA tables, spans, labels/external form controls, JSON-LD, canvas, omitted private values, depth/node/frame limits and malformed data. Local server exceptions are test-injected only.

### Frames without Window slots — CHG-20261013-028

A shadow frame may be absent from window.frames. The reader then requires a CDP session for that exact frame; DOM.getFrameOwner distinguishes its target root from local descendants without transferring FrameTree/TargetInfo, titles or URLs. A unique root, mounted owner and unchanged context are checked before/after capture. Ancestor/page sessions and missing/ambiguous roots are refused. Diagnostics: path_source=frame_target_root, failure=target_root_ambiguous; optional stale_candidate_count 0–128, absent means unknown.

Visibility is checked before scheme: hidden is omitted/hidden_frame without content read; visible blob is unavailable/unsupported_frame_scheme. Select options are capped at 300; overrun is partial/options. Form values stay excluded. No solver or approval transfer.


## Fresh capture after navigation mutation — Greenfield fix

An unpublished capture interrupted by NAVIGATION_CHANGED may be recaptured at
most twice within the same job, only while its URL equals the checkpoint URL
and passes the scope guard. Each recapture checks authorization, waits250ms,
and reads a fresh snapshot; no navigation or client POST replay. No further
recapture is started after the navigation budget expires. A changed URL or
persistent drift remains rejected without an artifact. capture_restarts reports
recaptures in the receipt. Partial content and network refusals remain explicit.
See the [Greenfield report (French)](GREENFIELD_EXPORT_REPORT.md).


## Clearpath four-video frame budget fix

Eight visible documents including main now fit within the unchanged40s global and10s per-frame budgets. Overflow, hidden-frame inventory32 and internal truncation remain explicit. Four mounted video frames are read completely. Runtime/source hashes, tests and real no-fallback verification: [Clearpath report](CLEARPATH_EXPORT_REPORT.md).
