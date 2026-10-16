# PageQuay interface screenshots

[Français](SCREENSHOTS.md) | [English](SCREENSHOTS.en.md)

Captured October 16, 2026 from PageQuay sources in a **disposable instance**, with two fictitious projects and synthetic data. Charts show illustrative volumes, not production measurements. The interface is in French.

Key prefixes, tab IDs, audit actors, URLs and local addresses are covered by opaque masks. Audit job IDs are replaced in the disposable document before capture. No installed service, personal profile, existing key or real Tailscale state was read. Published PNGs were visually inspected; working files, databases, profiles and temporary secrets are not distributed.

## Overview

Two independent profiles, illustrative API activity and disposable-profile disk usage.

![Overview with two fictitious projects](screenshots/overview.png)

## Projects / Profiles

Project creation, browser management and profile separation.

![Demo project and profile management](screenshots/projects.png)

## API keys

Permissions, quotas and expiry. Full secrets are never displayed and prefixes are masked.

![API key management with masked prefixes](screenshots/api-keys.png)

## Sessions / Tabs

Tabs from two projects with IDs/URLs masked. Minimize buttons are disabled because the demonstration browsers run headless.

![Sessions and tabs with masked IDs and URLs](screenshots/sessions.png)

## Search

DuckDuckGo form with country/time filters. The example query was not submitted to an external engine.

![DuckDuckGo search with country and time filters](screenshots/search.png)

## Settings

Upper settings sections: local ports and external access. Local addresses/ports are masked; this instance has no external access configured.

![Settings with local addresses and ports masked](screenshots/settings.png)

## Audit

Demo events and filters without readable private actors, URLs or IDs. The table scrolls horizontally; rightmost columns may be outside the view.

![Audit with actors, URLs and identifiers redacted](screenshots/audit.png)

## Mobile view

Sessions / Tabs in a 390-pixel-wide viewport.

![Sessions and tabs on mobile](screenshots/sessions-mobile.png)

## Reproduce the screenshots

From the repository root with development dependencies and Chromium installed:

```sh
.venv/bin/python scripts/capture_screenshots.py
```

The script creates a temporary database/profiles, starts a disposable loopback-only instance, captures PNGs and closes browsers/server. Demonstration example.org pages are fulfilled locally without external fetching. Tailscale status is synthetic; its CLI is never called. A demonstration banner is added to captured documents, and masks are applied before writing each image. Visually inspect regenerated captures before publishing, especially after layout changes.
