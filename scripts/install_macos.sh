#!/bin/zsh
set -euo pipefail
cd "${0:A:h:h}"
if [[ "$(uname -s)" != "Darwin" ]]; then
  print -u2 "This installer targets macOS."; exit 1
fi
if command -v uv >/dev/null 2>&1; then
  uv sync --frozen --extra dev
else
  python3 -m venv .venv
  .venv/bin/python -m pip install -e '.[dev]'
fi
.venv/bin/playwright install chromium
.venv/bin/pq migrate
print "Installation complete. Create your administrator: .venv/bin/pq init-admin"
