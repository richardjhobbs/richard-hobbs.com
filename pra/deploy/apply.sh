#!/usr/bin/env bash
# Runs on the VPS as root on every deploy (the workflow calls it with sudo). Safe to run repeatedly.
# Keeps the nginx redirect snippet and the systemd unit in step with the repo, and installs the
# production vhost for pacificriskadvisors.com the first time only.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
SNIPPET=/etc/nginx/snippets/pra-redirects.conf
AVAILABLE=/etc/nginx/sites-available/pacificriskadvisors.com
ENABLED=/etc/nginx/sites-enabled/pacificriskadvisors.com
UNIT=/etc/systemd/system/pra-mcp.service

# systemd unit
if ! cmp -s "$HERE/pra-mcp.service" "$UNIT"; then
  cp "$HERE/pra-mcp.service" "$UNIT"
  systemctl daemon-reload
  echo "pra-mcp unit updated"
fi

# nginx: redirect snippet (always refreshed) and production vhost (first time only)
mkdir -p /etc/nginx/snippets
had_snippet=no
if [ -f "$SNIPPET" ]; then cp "$SNIPPET" "$SNIPPET.bak"; had_snippet=yes; fi
cp "$HERE/pra-redirects.conf" "$SNIPPET"

new_vhost=no
if [ ! -f "$AVAILABLE" ]; then
  cp "$HERE/nginx-prod.conf" "$AVAILABLE"
  ln -sf "$AVAILABLE" "$ENABLED"
  new_vhost=yes
fi

if nginx -t; then
  systemctl reload nginx
  echo "nginx reloaded"
else
  # put things back so a bad file never blocks a later reload for the other sites on this server
  if [ "$had_snippet" = yes ]; then cp "$SNIPPET.bak" "$SNIPPET"; fi
  if [ "$new_vhost" = yes ]; then unlink "$ENABLED"; unlink "$AVAILABLE"; fi
  echo "nginx config test failed, previous configuration kept"
  exit 1
fi
