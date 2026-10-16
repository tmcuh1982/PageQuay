# AgXeed UNAVAILABLE fix — October 13, 2026

[Français](AGXEED_READ_FIX.md) | [English](AGXEED_READ_FIX.en.md)

UniversRobot requested log inspection, correction/retest and later GitHub commit/push. Installed service 0.2.2, active graphical session; keys/profile preserved.

Historical readonly-SQLite evidence: https://www.agxeed.com/, navigation job 005425b5c8c68f2031f7079c301cd37a, request e24970adf026c4035e1b5070, tab a0d63808962b3619107c13b19b7d6dd4. At 16:48:56.109821 UTC: UNAVAILABLE / Document unavailable during extraction, WORLD_NOT_FOUND at isolated_world, three candidates/zero probes.

Reader previously aborted when any CDP candidate vanished. It now continues only on WORLD_NOT_FOUND **before capture**. Other errors block; selected context/frame position are rechecked after capture without page-JavaScript fallback. test_stale_candidate.py failed before and passes after.

First retest hit NAVIGATION_CHANGED during title capture: job b587457a8ff457fdc3c708993c98d379, request 9773c4f2ce82ad37efbd36d9, 16:55:51–16:55:59 UTC. navigation_title discards the unpublished title and retries within the original deadline, rechecking challenge/exact scope/network and total timeout. No retry of incoherent exports or broader approval.

Recipe: create the exact URL with POST /v1/projects/{project}/tabs, poll/check final URL, then structured content with exact expected_url. Load existing credentials privately; never display Bearer/cookies. UniversRobot used asyncio.run(pagequay_page.read('https://www.agxeed.com/',allow_truncated_strings=True)), one attempt, expecting coherent export or typed human wait.

Retests 16:58:36.957620–16:58:54.653239 and 16:58:54.653400–16:59:07.224709 UTC no longer returned UNAVAILABLE; both waited for human extraction confirmation. Jobs 83636965f17bbb34a8ec3bdf5db563ef / 71cbece8e2bf5e9ee578c57fd0fe0011; requests 700501adc59312569c314c94 / 243e41691fd9fced14919796; tabs a7d1a0d88489756f4dfa3ff2d44d705a / 93afa2153d87fe5a4c24169718960d8a. No artifact/frame in response; test tabs closed. No full export/CAPTCHA solving/model calls claimed. KUKA control completed in 10.484 seconds, partial=false.

Validation: general 232 passed/44 skipped, 43 targeted real Chromium, five unit regressions/Ruff pass; 99 UniversRobot client tests. Client now preserves UNAVAILABLE and known cause/read_stage without arbitrary exception text. Sets overlap.

Changed page_reader.py/browser.py, stale/title tests and this note. Two Python files deployed after tests/zero jobs, private /private/tmp/ur-installed-{page-reader,browser}-before023.py backups, launchctl kickstart. No key/config/profile changes. CHG-20261013-023 / TODO-081 completed; human follow-up TODO-075 separate.
