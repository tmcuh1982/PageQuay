# CAPTCHA widget versus main challenge — October 13, 2026

[Français](CAPTCHA_WIDGET_FIX.md) | [English](CAPTCHA_WIDGET_FIX.en.md)

UniversRobot requested completing AgXeed Ask IA. User confirmed normal page in Jump Desktop, yet extraction waited for a human: old job 836bf8d624cb1a5d45d517e76917ae10, tab deae0e88bd2985b0778902496bff568e, request 0d9fe12faeef57c2da35e385.

Cause: mere recaptcha/hcaptcha iframe presence was treated as a blocking challenge. An invisible frame/small form widget does not prove the main document is blocked.

Fix: a frame blocks only with explicit data-pq-challenge or a visible CAPTCHA iframe covering at least 50% of viewport. captcha_widget records presence separately. Scan is bounded to 32 widgets. Explicit human messages and automatic/Cloudflare signals remain in challenge_state. No CAPTCHA solving or omitted iframe export. Geometry is heuristic, not proof that all challenges are absent. Scope/coherence guards remain.

```sh
PYTHONPATH=src .venv/bin/python -m pytest -q --browser tests/test_captcha_widget.py
```

Invisible/small widget cases failed before (two failed/four passed), all passed after, including fullscreen/explicit marker/human/automatic cases. Targeted challenges/acquisition: 38 passed; general: 232 passed/50 skipped; Ruff conformant.

Real authenticated Ask IA recipe on https://www.agxeed.com/, one attempt, patched PQ 0.2.2 and active Mac mini GUI: no longer waiting_for_human. A separate export-budget defect then failed protocol validation with absent URL and frame_limit/string_length/text_budget/node_limit. Job cb1a20ac2ebd1c63f7afbbf62f518f03, tab 9992df4883ceb1d12cf73585f150c3ba, request 328040d6efe4a2a86a8f39bb, artifact 7324551f36b79ef2b2fca4650957896c; October 13, 2026, 19:22:35.281001–19:22:35.595077 Europe/Warsaw. No model call. Existing TODO-070 tracks export. Keys/profile unchanged; restart after zero jobs, private /private/tmp/ur-reader-before025.js backup. Files: page_reader.js, test_captcha_widget.py, this note. CHG-20261013-025 / TODO-082.
