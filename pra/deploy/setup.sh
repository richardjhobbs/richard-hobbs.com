#!/usr/bin/env bash
# One-time setup on the VPS for pra.richard-hobbs.com. Run as a sudo user from this directory,
# after the files are in /var/www/pra.richard-hobbs.com (the GitHub deploy does that on merge to main,
# or copy pra/site and pra/mcp there by hand).
set -euo pipefail

ROOT=/var/www/pra.richard-hobbs.com
DEPLOY_USER=${DEPLOY_USER:-agent}
HERE=$(cd "$(dirname "$0")" && pwd)

command -v python3 >/dev/null || { echo "python3 is required"; exit 1; }
command -v certbot >/dev/null || { echo "certbot is required"; exit 1; }

sudo mkdir -p "$ROOT/site" "$ROOT/mcp" /var/lib/pra-mcp
sudo chown -R "$DEPLOY_USER":"$DEPLOY_USER" "$ROOT" /var/lib/pra-mcp
sudo chmod 750 /var/lib/pra-mcp

sudo cp "$HERE/nginx.conf" /etc/nginx/sites-available/pra.richard-hobbs.com
sudo ln -sf /etc/nginx/sites-available/pra.richard-hobbs.com /etc/nginx/sites-enabled/pra.richard-hobbs.com
if ! sudo nginx -t; then
  sudo rm -f /etc/nginx/sites-enabled/pra.richard-hobbs.com
  echo "nginx config test failed, vhost not enabled"; exit 1
fi
sudo systemctl reload nginx

sudo cp "$HERE/pra-mcp.service" /etc/systemd/system/pra-mcp.service
sudo systemctl daemon-reload
if [ -f "$ROOT/mcp/server.py" ]; then
  sudo systemctl enable --now pra-mcp
else
  sudo systemctl enable pra-mcp
  echo "server.py is not in $ROOT/mcp yet. Start the service after the first deploy: sudo systemctl start pra-mcp"
fi

sudo certbot --nginx -n -d pra.richard-hobbs.com --redirect

echo "Done. Check: curl -s https://pra.richard-hobbs.com/healthz"
