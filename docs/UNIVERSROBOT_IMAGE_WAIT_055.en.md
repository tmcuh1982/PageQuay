# Bounded image response wait — CHG-20261025-055

[Français](UNIVERSROBOT_IMAGE_WAIT_055.md) | [English](UNIVERSROBOT_IMAGE_WAIT_055.en.md)

UniversRobot TODO-359. POST download_image?wait_seconds=0..10 returns a completed job with HTTP 200 or the same HTTP 202 ticket. Default asynchronous behavior is preserved. Access is rechecked after waiting; no replay or quota change. Applied to repository api.py and the installed 1.2.2 runtime. Private backups and detailed acceptance evidence remain outside the public repository. No profiles, secrets or business database were changed.
