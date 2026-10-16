# Browser startup diagnostics

[Français](STARTUP_DIAGNOSTICS.md) | [English](STARTUP_DIAGNOSTICS.en.md)

BROWSER_CRASHED keeps its compatible code/message and adds stage=startup, startup_step and a bounded cause. No raw exception, profile/executable path, Chromium command or environment variables.

Steps: proxy_start, playwright_start, selector_registration, browser_launch, browser_setup. Existing typed PQ errors and cancellation remain unchanged, as do proxy/context cleanup and application-lock release.

Recognized browser_launch causes: BROWSER_LAUNCH_TIMEOUT (Playwright Timeout), BROWSER_EXECUTABLE_MISSING (anchored launch message), BROWSER_PROFILE_LOCK_EXISTS (SingletonLock: File exists marker in launch error). A lock file does not prove a live old process. Others remain UNKNOWN_STARTUP_FAILURE with known step and bounded PLAYWRIGHT_ERROR/PLAYWRIGHT_TIMEOUT/OTHER class. No profile deletion, key reset or automatic headless fallback.

## Reproduction without installed profiles/keys

Requires PQ Python/Playwright, startup_diagnostics code and available driver. Before the fix (b7c61ec), manager launch timeouts lacked details, giving a failing regression.

```sh
PQ_BROWSER_TESTS=1 PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_startup_diagnostics.py -q
```

The real test calls BrowserManager.start with a synthetic project/temporary profile, real Playwright, absent temporary executable and simulated proxy. No navigation target: startup fails before about:blank/HTTP. Expected BROWSER_CRASHED/browser_launch/missing-executable, no path disclosure, closed proxy and reacquirable application lock. These checks passed on the Mac mini. Request/job/tab/frame/artifact are not applicable to direct manager calls; execution correlation comes from test delivery evidence, not invented IDs.

Synthetic tests cover timeout/lock/missing and reject navigation markers/wrong exception classes/SECRET text. Two real contexts did not reproduce a Chromium lock on the tested version: the second launch succeeded, so that cause has controlled-message coverage only, without inferred historical cause.

For installed incidents retain exact public URL, date/version, returned IDs and bounded step/cause. UNKNOWN remains unknown: request correlated private logs without publicly attaching keys/cookies/profiles/raw exceptions. Success after session change and restart does not isolate a single prior cause.
