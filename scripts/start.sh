#!/bin/zsh
set -euo pipefail
cd "${0:A:h:h}"
if [[ ! -x .venv/bin/pq ]]; then
  print -u2 "Missing environment; run scripts/install_macos.sh"; exit 1
fi
exec .venv/bin/pq serve
