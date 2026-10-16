# AgXeed export identity under budget — October 13, 2026

[Français](AGXEED_EXPORT_FIX.md) | [English](AGXEED_EXPORT_FIX.en.md)

UniversRobot requested TODO-070 completion through DeepSeek/Jev advisory results and publishing fixes/tests. Keys/profile/config/approvals preserved.

## Defect and correction

Before: https://www.agxeed.com/ exhausted 2000 nodes/40000 characters, empty URL/title and text_budget/nodes/string_length/frame_limit_reached. Job cb1a20ac2ebd1c63f7afbbf62f518f03, request 328040d6efe4a2a86a8f39bb, tab 9992df4883ceb1d12cf73585f150c3ba, artifact 7324551f36b79ef2b2fca4650957896c; October 13, 2026, 19:22:35.281001–19:22:35.595077 Europe/Warsaw.

Identity was copied after DOM exhausted its shared budget. URL/title now reserve budget before metadata/DOM; URL 2048/title 500 limits remain. Invalid identity is never replaced with an invented URL.

Per-document limits recalibrated to 8000 visited nodes and min(160000,max_content_bytes/8) characters; depth 32/other limits remain. Actual export measured 4221 nodes/80281 characters, exceeding old capacity. At most four visible documents including main; inventory 32. Hidden frames are omitted/hidden_frame without consuming reads. Inventory/visible overrun stays partial/frame_limit_reached. Global 40 seconds, 10/frame, typed global TIMEOUT rather than false success. Context/scope/challenge/artifact guards remain.

## Reproduction and evidence

Requires patched installed PQ 0.2.2, active Mac mini GUI and existing private credentials. UniversRobot authenticated source 3f1ce16b-fa8e-57c4-a215-6c01c134d42a, exact https://www.agxeed.com/, Ask IA once without automatic replay. Expected intact identity and usable bounded advisory export, with limits flagged.

After: job d44e22124a6c834a23fcd5f4523bb1e7, request d27f53ee3c4b34137b5d55ca, tab ba95a59c46fbf310016576705dbbc43c, artifact 73f86e7dd5d8cb53c645b256eefa0c6a. Exact URL, title Home - AgXeed.com, 87361 bytes; 4221 visited/3156 included nodes, 80281 characters, frame_limit_reached=false; two children extracted/eight hidden omitted. Only string_length truncation remains; no global text/node limit or unavailable frame. String truncation was permitted for advisory use only, not a complete business extraction claim.

Ask IA completed October 13 at 19:47:56.902529 Europe/Warsaw: deepseek-flash and jev-1.13.0 both returned organization. DeepSeek suggested approved for the manufacturer home; no human decision/publication applied. Audit 89f6c5ad-54e9-4bf6-9ec3-0eb92f699956; model requests aa64a5aa-1fe1-41f7-9ab4-c20202c32d02 / 139be01d-475a-4070-a9b8-6a6e809ba3db. Canonical JSON SHA-256 dcae5a4743448dcb81929520f8821f296ff299feefe131d7690316dc07c700ce matches downloaded export/audit.

Tests: failing pre-fix identity/DOM/hidden/visible regressions; six final including 32-frame inventory/timeout; 40 targeted Chromium/acquisition guard tests pass; general 233 passed/55 skipped. Ruff/format/node syntax pass. Oversized fixtures still exceed new bounds and preserve node/depth/visible-limit signals.

Files: extraction.js, structured.py, export budget/deadline/structured tests and documentation. Two runtime sources copied after testing, private /private/tmp/pq-extraction-before026.js and pq-structured-before026.py backups, zero-job restart. CHG-20261013-026 / TODO-070; no package/migration/key/profile added.
