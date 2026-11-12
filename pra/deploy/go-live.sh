#!/usr/bin/env bash
# Run once on the VPS, as a sudo user, AFTER the DNS for pacificriskadvisors.com and
# www.pacificriskadvisors.com points at this server. Issues the certificate and turns on HTTPS.
set -euo pipefail

IP=$(curl -fsS https://api.ipify.org)
for name in pacificriskadvisors.com www.pacificriskadvisors.com; do
  if ! getent ahostsv4 "$name" | awk '{print $1}' | grep -qx "$IP"; then
    echo "$name does not point at this server ($IP) yet. Change the DNS first, wait for it to take effect, then run this again."
    exit 1
  fi
done

sudo certbot --nginx -n -d www.pacificriskadvisors.com -d pacificriskadvisors.com --redirect
curl -fsS https://www.pacificriskadvisors.com/healthz && echo && echo "Live at https://www.pacificriskadvisors.com"
