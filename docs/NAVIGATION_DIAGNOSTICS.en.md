# Navigation diagnostics

[Français](NAVIGATION_DIAGNOSTICS.md) | [English](NAVIGATION_DIAGNOSTICS.en.md)

Chromium-refused navigation remains refused. PageQuay keeps UPSTREAM_UNAVAILABLE and the generic “Navigation failed” message, adding details only when the first line of Page.goto's error contains a recognized network code:

```json
{"cause":"TLS_CERTIFICATE_DATE_INVALID","stage":"navigation","browser_error":"ERR_CERT_DATE_INVALID"}
```

This means an invalid TLS validity period; it alone does not distinguish expired from not-yet-valid. No URL, raw exception, call log or header is copied. JavaScript errors, call-log mentions, unknown codes and other call sites are not interpreted as network diagnostics. Existing refusal/timeout/crash classifications remain. Certificates are never ignored.

## TM Robot reproduction

Exact URL: https://www2.tm-robot.com/zh-hant/tm-robot/. Use an existing service/key with browser:interact and job access, without copying secrets into logs. Create a tab with allow_redirects=true and poll the job. On October 14, 2026, the observed expired certificate produced failed/UPSTREAM_UNAVAILABLE and the details above, with no extracted content. Renewal can legitimately change the result.

A disposable service/profile produced job e0ee802ddb201290b56775325f906ae8, tab f28ce658458781e0301f7246705ab616, request 6bd3a8bb61bdf84222e3dd5b with expected details. Initial source af4642f plus the patch; no existing installation/key changed. No artifact/frame was available.

## Verification

BrowserManager.navigate call-site tests preserve timeout/crash behavior and exclude URLs/call logs. Historical suite: 245 passed, 63 skipped; disposable real-Chromium API recipe was separate. This change does not repair the site's certificate or approve another URL.
