# Browser transport and WebSockets — 0.2.4

[Français](BROWSER_TRANSPORT.md) | [English](BROWSER_TRANSPORT.en.md)

## Behavior

Each project keeps a separate persistent profile. PQ_BROWSER_CHANNEL=chromium is default, using Playwright's browser (possibly named “Google Chrome for Testing” on macOS); chrome selects Google Chrome in /Applications. No personal profile is used.

launch_persistent_context and Playwright initialization remain. A local relay terminates the internal pipe and talks to its child on an explicit nonzero launch-selected CDP port bound to 127.0.0.1. The advertised endpoint must match the child's expected address/port. Chrome receives no pipe. The private temporary wrapper and child are cleaned on stop/cancel/EOF/failure. The control port is never exposed by API/Serve and is for trusted local processes only.

Sandbox, public-IP proxy, routing/redirect checks, Service Worker/permission/download denial, disabled QUIC/unproxied UDP WebRTC remain. The relay directly depends on websockets>=15,<18.

## Native WebSocket denial

```text
http=http://127.0.0.1:<public>;https=http://127.0.0.1:<public>;socks=http://127.0.0.1:<deny>
```

Chromium's socks= means “other proxies”; explicit http:// avoids SOCKS4 interpretation. ws/wss use this category ([official rules](https://chromium.googlesource.com/chromium/src/+/HEAD/net/docs/proxy.md#mapping-websockets-urls-to-a-proxy)). The deny listener returns 403 before DNS/upstream connection. No alternative/direct fallback. JavaScript WebSocket remains native; context.route_web_socket is removed. PQ's command WebSocket remains available.

Real Chrome/Chromium tests prove positive unguarded ws/wss then guarded refusal with no upstream handshake, covering same/cross-origin frames, srcdoc, popups, dedicated/shared workers, native constructor, continued HTTP/HTTPS and denial after stopping the listener. Proxy tests cover pre-DNS refusal, client shutdown and second-bind failure cleanup; relay tests cover endpoint, transport and child cleanup.

## Music Store diagnosis — October 14, 2026

Controlled comparisons preserved other guards: three full controls blocked; three succeeded removing only route_web_socket; two remained blocked with simple passthrough routing. This suggests instrumentation affected this site, not a general proof of Cloudflare's internal rule. Explicit CDP alone had not sufficed.

Observed versions: Playwright 1.63.0, installed Chrome 155.0.8059.80, bundled Chromium 153.0.8010.12. After runtime deployment, search “test”, cookie acceptance and Yamaha P-45 page succeeded in fresh Chrome then Chromium profiles, HTTP 200, preserving process per journey. An incomplete process check was corrected and revalidated.

A fresh Chromium service profile stayed open. “test”/Yamaha P-45 then “Shure SM58”/Shure BLX2/SM58 S8 succeeded using the existing test key, same process/tab. Cookies accepted and window restored. Five additional searches in the same session:

| Search | Product page | Search/page HTTP |
| --- | --- | --- |
| Fender Stratocaster | Fender American Professional Stratocaster MN Black | 200/200 |
| AKG K240 | AKG K240 MKII | 200/200 |
| Focusrite Scarlett | Focusrite Scarlett 2i2 4th Gen | 200/200 |
| Yamaha HS5 | Yamaha HS 5 | 200/200 |
| Roland FP10 | Roland FP-10 BK | 200/200 |

First Fender click timed out without detected challenge. The loaded search was retained; five product pages were then opened by API navigation to observed result links. Titles/content/statuses were checked against evidence/audit. This validates five navigations, not five successful clicks. No challenge was observed; same process/tab stayed on the final product.

## Historical deployment and limits

Runtime sources/dependency were deployed with private backup, zero-active-job stop and readiness checks. Settings/scopes/keys were preserved; normal activity fields changed. Old test profiles were backed up separately. At this historical stage service channel remained Chromium and installed metadata 0.2.2 while the checkout prepared 0.2.4. The release commit neither reinstalled the package nor restarted the retained window.

Results are site/network/version/session-specific, with no guarantee of future challenge-free access. No CAPTCHA solving. Detection is imperfect; HTTP/title/content supplement observation. The proxy is not an OS firewall. Raw reports/captures/profiles/secrets stay private. Configured idle timeout can still close a browser left open by a test script.
