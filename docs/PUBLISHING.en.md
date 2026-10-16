# Publishing and synchronizing PageQuay

[Français](PUBLISHING.md) | [English](PUBLISHING.en.md)

Target: public [tmcuh1982/PageQuay](https://github.com/tmcuh1982/PageQuay), main branch. Public publication was explicitly authorized. Local origin uses HTTPS and main tracks origin/main.

## GitHub access

The repository owner has write permission. Historically the app connector returned 403 Resource not accessible by integration even after reconnection, so publication used authenticated GitHub CLI 2.102.0 on the mini. For another installation:

```sh
gh auth login --hostname github.com --git-protocol https --web
gh api user --jq .login
git config --local credential.https://github.com.helper ''
git config --local --add credential.https://github.com.helper '!gh auth git-credential'
```

Validate the browser login under the intended account and verify returned login before publication. Credential helper is repository-local; the mini uses the installed absolute executable path. Do not copy passwords/tokens/private keys into docs/chat. Reading public sources needs no credentials.

In that historical environment, CLI credentials were stored outside the project in a 0600 file rather than the system keychain. Never include it in public backups/repository.

## Versioned content and bilingual documentation

Tracked content: src, tests/fixtures, scripts/examples, pyproject.toml, uv.lock, README/security/docs and development records memory.md/decisions.md. .gitignore excludes environments, .env secrets, SQLite, profiles/artifacts/backups/logs/local diagnostics. .env.example is secret-free. Only explicitly allowed test reports and fixture JSON are tracked under docs/testing; inspect the current .gitignore rather than assuming every report is publishable. Ignore rules do not untrack existing files.

Public guides, release notes, published validation reports and original references have French .md and English .en.md versions linked in [the index](README.md). Update both whenever behavior or evidence changes; preserve endpoint names, JSON keys, commands, versions, timestamps and measured results. OpenAPI/code/JSON fixtures are shared. Original specifications remain historical requirements, not delivery evidence. Internal memory.md/decisions.md development journals remain French and are separate from public guides.

## Local then remote update

```sh
git status --short --branch
git fetch origin main
git log --oneline origin/main..HEAD
git diff --check
```

Document only actually delivered functionality/observed validation. Record decisions/resumption state in the development journals when relevant. Run appropriate checks after code changes; documentation-only changes do not justify rerunning all browsers. Review tracked/staged files before publication.

```sh
git add README.md README.en.md SECURITY.md SECURITY.en.md docs
git diff --cached --check
git diff --cached --stat
git commit -m "Update bilingual PageQuay documentation"
git push origin main
```

Inspect any already staged changes. Normal push preserves history; no force push is needed. If remote advanced, review/integrate before publishing. API publication, when authorized and functional, must retain remote parent/executable modes, verify branch head, fetch public commits locally and compare content before history alignment.

## Verification

```sh
git fetch origin main
git rev-parse HEAD
git rev-parse origin/main
git diff HEAD origin/main -- README.md README.en.md SECURITY.md SECURITY.en.md docs
git status --short --branch
```

Full pushes should leave identical commits and a clean checkout. If only documents were published by API, compare those explicitly; it does not prove code publication. Update status/memory only from confirmed results. Repository publication installs neither LaunchAgent nor Serve and does not start the service.

The stable 1.1.0 release was published on October 16, 2026 from 11ce7dd with wheel, sdist and verified SHA256SUMS. Subsequent documentation updates on main do not alter immutable release packages/tagged sources. GitHub release descriptions can link current bilingual documentation.
