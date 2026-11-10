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
