# RECETTE — original verifiable acceptance checklist

[Français](RECETTE.md) | [English](RECETTE.en.md)

Historical requirements, **not completed-test claims**. Run unit/integration tests on localhost. No Google/Brave/DDG account or Cloudflare bypass is needed to validate security; live engines are additional diagnostics, not guaranteed. Actual evidence is in [the report](../testing/REPORT.en.md).

## Security/authentication

- [ ] No anonymous/default admin; explicit bootstrap CLI and Argon2id SQLite hash.
- [ ] Invalid login rejected/rate-limited without revealing information.
- [ ] Admin session/CSRF, escaped remote HTML/XSS protection.
- [ ] ProjectX key can access only its scoped project, not project-b.
- [ ] Project-b cannot access ProjectX tabs/jobs/screenshots/WS even with known IDs.
- [ ] Expired/revoked key rejected 401/403; existing WS invalidated at next check.
- [ ] Full secret only shown at creation, absent from plaintext DB/log/listing.
- [ ] Localhost, 192.168.1.1, 10.0.0.1, 169.254.169.254 and private redirect denied; test IPv6/private DNS.
- [ ] No network-accessible CDP; FastAPI default loopback only.
- [ ] Operational rate/payload/job limits.

## Browsers/profiles

- [ ] Two projects with separate persistent directories and simultaneous graphical browsers.
- [ ] Test cookie never crosses projects; local-network exception is explicit/test-only, never production.
- [ ] Restart ProjectX preserves its cookie and leaves project-b unchanged.
- [ ] Same user_data_dir never launches corrupting concurrent Chrome; conflict/reuse.
- [ ] Allowed public navigation/rendered DOM/text/links/metadata/screenshot with proper scope.
- [ ] Read-only keys cannot click/fill; authorized keys can on fixtures.
- [ ] Simulated challenge enters human wait, preserves tab and resumes on test signal without solver.
- [ ] Simulated browser crash has coherent state and leaves neighboring project usable.

## Retention/reset

- [ ] Content TTL purges cache without deleting persistent session cookies.
- [ ] Browser idle closes without deleting profile and reopens on demand, subject to site validity.
- [ ] Soft restart preserves profile and defers active work.
- [ ] Hard reset requires two admin confirmations, deletes only correct directory, waits for drain/cancel and audits.
- [ ] Audit/artifact retention and purge are testable.

## Search/API

- [ ] Google/Brave/DDG adapters tested using fixtures, changed HTML/empty results handled.
- [ ] Multi-engine deduplication preserves provenance/stable order.
- [ ] Query/limit/timeouts/structured errors validated.
- [ ] WS announces job events and accepts only authorized interactions.
- [ ] Search/job routes isolated by project.
- [ ] Optional live DDG produces results or honest diagnostic for engine change/limits.

## macOS operations

- [ ] Local startup without Docker/SaaS/hardcoded secrets.
- [ ] LaunchAgent tested or explicitly documented untested if no Mac available.
- [ ] Playwright Chromium install/doctor show useful errors.
- [ ] Private HTTPS/Serve documentation, no public default exposure.
- [ ] README, secret-free .env.example, SECURITY, component diagram, commands and backup procedure provided.

Final report must list actual tests/results, items not locally verifiable and remaining deviations. Never mark unexecuted tests as passed.
