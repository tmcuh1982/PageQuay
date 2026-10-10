#!/bin/zsh
set -euo pipefail
label="local.pagequay.gateway"
if launchctl print "gui/$(id -u)/$label" >/dev/null 2>&1; then
  launchctl bootout "gui/$(id -u)/$label"
  print "PageQuay LaunchAgent unloaded. Profiles retained."
else
  print "No loaded PageQuay LaunchAgent. For a foreground instance use Ctrl-C in its terminal."
fi
