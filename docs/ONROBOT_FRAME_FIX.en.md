# OnRobot RG2 frames and options — CHG-20261013-028

[Français](ONROBOT_FRAME_FIX.md) | [English](ONROBOT_FRAME_FIX.en.md)

Scope: source/extraction tickets TODO-068 (frame), TODO-083 (options), TODO-084 (diagnostic schema). No solver/key/profile/permission/approval changes.

## Reproduction and defects

Patched installed PQ 0.2.2, active Mac mini GUI and existing private credentials; exact https://onrobot.com/en/products/rg2-finger-gripper. Authenticated UniversRobot dossier 05f69388-e8da-53d3-be21-ae1a1d4c5b6a → Ask IA once. Probe opens URL, checks exact tab URL, requests structured expected_url and downloads. Before: partial_content prevented model invocation.

October 13, 2026, 20:23:51.939063–20:23:58.335257 Europe/Warsaw: job ab32886b5bd4d7e94cfe03177e2e88ff, request f946570d51a8d1885ecfabda, tab 173e265159feb6045e6375496e80d4c3, artifact e8898990e6e5cb9ece8cc4f1f79b22da. f1 WORLD_NOT_FOUND/context_selection/unattached; f2 unsupported_frame_scheme/blob; main 2751 nodes/43541 characters, options truncation, no node saturation after CHG-026.

Chromium reproduces a cross-site iframe in open/closed Shadow DOM with window.frames.length=0 despite attachment. Slot mapping cannot identify it. The site had the same unmapped-owner signature and corrected frame_target_root selection; the site's exact Shadow DOM mode is not inferred from a Cloudflare URL.

## Fixes and preserved refusals

Unmapped frames require a CDP session bound to that exact frame. DOM.getFrameOwner opaque IDs distinguish local descendants; native “Frame with the given id does not belong to the target” identifies root owner outside target. Root must be unique, owner mounted and context unchanged before/after. No first-context/URL/title guess, FrameTree/TargetInfo or page-JavaScript fallback. Ancestor/page sessions, missing/ambiguous roots, moved owner/context loss remain refused. Insufficient in-process identity stays unavailable.

Visibility precedes scheme: hidden blob f2 becomes omitted/hidden_frame without content read; visible blob remains unavailable. Closed parent DOM is not traversed, but independently known frame documents may be read when identity verifies.

250 mounted form options exceeded the previous 100 export cap; new cap 300 textual options, with 350 still partial/options. value/input/textarea values stay excluded; node/text/byte quotas unchanged. UniversRobot reports option-limit cause without permitting more partial content.

Diagnostics add path_source=frame_target_root, failure=target_root_ambiguous. Previously emitted stale_candidate_count failed strict model validation as extra_forbidden; it is now optional 0–128, absent=unknown. Public OpenAPI regenerated/compared to installed listener.

## Live result and validation

October 13, 20:56:54.585200–20:57:04.050800 Warsaw: 9.465 seconds, 12 passages, partial=false. Ask IA at 20:58:21.149591+02: deepseek-flash and jev-1.13.0 returned accessory. DeepSeek suggested approved; no human decision applied. The quote described RG2's 110 mm stroke/programmed force, not Cloudflare content.

Audit e5abe750-f095-46ee-8591-1c0b8acf73ac; model requests 2d0e065d-17a3-4a28-82ed-b19f32219747 / a96403de-d925-48f2-be97-173669dff127. Export job d07a4403490c9a345c2fc89e749ccd3b, request 93c7da912644465d8283c6e8, tab 165ecb4009371d906ecd0236db225a31, artifact 5225c1af713c09bb513354adedafe7ad. 52444 bytes, no partial/truncation; f1 extracted/frame_target_root, two contexts, f2 hidden omitted, 250 options. Canonical digest f7ddb2cd00a4f74810f5d26e1c3ab5e3827ae61926f11d1ef3a3359f94495aa3 matches audit. Bounded advisory excerpts do not imply incomplete source export.

48 targeted Chromium/guard tests; general 239 passed/63 skipped; 100 UniversRobot client tests. Coverage: red/green shadow frame, child/root distinction, missing/ambiguous roots/changed owner refusals, hidden/visible blobs, 250/350 options/no values, writer→strict model bounds/absence and OpenAPI. No added rights or increase in four-read/32-inventory quotas.
