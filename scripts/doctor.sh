#!/bin/zsh
set -euo pipefail
cd "${0:A:h:h}"
if [[ ! -x .venv/bin/pq ]]; then
  print -u2 "Missing .venv. Run scripts/install_macos.sh"; exit 1
fi
.venv/bin/pq doctor
if command -v tailscale >/dev/null 2>&1; then
  tailscale serve status
else
  print "Tailscale CLI not found; only needed for remote tailnet access."
fi
