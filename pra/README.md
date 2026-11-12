# Pacific Risk Advisors: site concept and MCP server

Review build for `pra.richard-hobbs.com`.

- `site/` static site. `index.html`, `agents.html`, and `data/knowledge.json`, the single content source for the pages and the MCP server.
- `mcp/server.py` public MCP server (Streamable HTTP, Python standard library only). Also takes the site's enquiry form at `/api/enquiry`.
- `deploy/` nginx vhost, systemd unit and a one-time `setup.sh`.

## Preview locally

```bash
python3 pra/mcp/server.py --static pra/site --port 8791
```

Then open http://127.0.0.1:8791/.

## Deploy

1. Merge to `main`. The workflow uploads `pra/deploy/` to `~/pra-deploy/` on the VPS, and copies the site and server to `/var/www/pra.richard-hobbs.com` once that folder exists.
2. First time only, on the VPS as a sudo user: `bash ~agent/pra-deploy/setup.sh` (creates the folder, nginx vhost, TLS certificate and the `pra-mcp` service). Then re-run the workflow and `sudo systemctl start pra-mcp`.
3. Content edits to `knowledge.json` go live on deploy with no restart. After a change to `server.py`: `sudo systemctl restart pra-mcp`.

Enquiries land in `/var/lib/pra-mcp/enquiries.jsonl` on the VPS. Nothing is emailed.

## Production (pacificriskadvisors.com)

Every deploy also builds a production copy (`deploy/build_prod.py`: no noindex, no review labels, sitemap added) into `site-prod/`, and `deploy/apply.sh` keeps a vhost for `www.pacificriskadvisors.com` and the old-address redirects in place on the VPS. Nothing is public until the DNS changes.

To go live:
1. At the DNS host, point the A record for `pacificriskadvisors.com` and `www` at the VPS. Leave the mail records alone.
2. On the VPS: `bash ~agent/pra-deploy/go-live.sh` (issues the certificate and turns on HTTPS).

Enquiry emails: create `/etc/pra-mcp.env` with `RESEND_API_KEY`, `PRA_NOTIFY_TO` and `PRA_NOTIFY_FROM`, then `sudo systemctl restart pra-mcp`. Without it enquiries are saved to `/var/lib/pra-mcp/enquiries.jsonl` only.
