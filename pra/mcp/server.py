#!/usr/bin/env python3
"""Pacific Risk Advisors public MCP server.

Model Context Protocol over Streamable HTTP, stateless, JSON responses.
Standard library only. Serves published information from site/data/knowledge.json
and takes enquiries into a local JSONL file for a person to review.

    python3 server.py                     # MCP on 127.0.0.1:8791, behind nginx
    python3 server.py --static ../site    # also serve the site (local preview)

Endpoints
    POST /mcp            JSON-RPC 2.0 (initialize, ping, tools/list, tools/call)
    POST /api/enquiry    Same enquiry store, for the site's own form
    GET  /healthz        Liveness
"""
import argparse
import json
import mimetypes
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
KNOWLEDGE = Path(os.environ.get("PRA_KNOWLEDGE", HERE.parent / "site" / "data" / "knowledge.json"))
ENQUIRIES = Path(os.environ.get("PRA_ENQUIRY_FILE", HERE / "enquiries.jsonl"))

SERVER_INFO = {"name": "pacific-risk-advisors", "title": "Pacific Risk Advisors", "version": "0.2.0"}
PROTOCOL_VERSIONS = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]
INSTRUCTIONS = (
    "Public information about Pacific Risk Advisors (PRA), ESG advisors to investors, multinationals and growing businesses. "
    "Use search_knowledge for a free-text question, list_capabilities and get_capability for services, "
    "and submit_enquiry only when the person you act for has asked you to contact PRA. "
    "This server holds published information only. It has no client data, fees or project records."
)

MAX_BODY = 64 * 1024
MAX_ENQUIRY_FILE = 5 * 1024 * 1024
RATE_LIMIT = 5          # enquiries
RATE_WINDOW = 3600      # per IP per hour

_lock = threading.Lock()
_cache = {"mtime": 0.0, "data": None}
_hits = {}


def knowledge():
    """Reload the knowledge file when it changes, so a content deploy needs no restart."""
    mtime = KNOWLEDGE.stat().st_mtime
    with _lock:
        if _cache["data"] is None or mtime != _cache["mtime"]:
            _cache["data"] = json.loads(KNOWLEDGE.read_text(encoding="utf-8"))
            _cache["mtime"] = mtime
        return _cache["data"]


# ---------------------------------------------------------------- search

STOP = set("a an and are as at be by can do does for from how i in is it my of on or our so that the "
           "their to us we what when where which who with would you your".split())


def tokens(text):
    return [t for t in re.findall(r"[a-z0-9&]+", text.lower()) if t not in STOP and len(t) > 1]


def search(query, limit=3):
    k = knowledge()
    q = set(tokens(query))
    if not q:
        return []
    scored = []
    for f in k["faqs"]:
        kw = set(f["keywords"])
        score = 2 * len(q & kw) + len(q & set(tokens(f["q"])))
        if score:
            scored.append((score, {"type": "answer", "question": f["q"], "answer": f["a"]}))
    for c in k["capabilities"]:
        name_hits = len(q & set(tokens(c["name"])))
        body_hits = len(q & set(tokens(c["summary"] + " " + " ".join(c["includes"]))))
        score = 3 * name_hits + body_hits
        if score:
            scored.append((score, {"type": "capability", "id": c["id"], "name": c["name"],
                                   "summary": c["summary"], "includes": c["includes"]}))
    for region in k["coverage"]:
        for country in region["countries"]:
            if set(tokens(country)) <= q:
                scored.append((4, {"type": "coverage", "country": country, "region": region["region"],
                                   "note": f"PRA has advisors in {country}."}))
    scored.sort(key=lambda s: -s[0])
    return [item for _, item in scored[:limit]]


# ---------------------------------------------------------------- enquiries

class EnquiryError(Exception):
    pass


def clean(value, limit):
    value = re.sub(r"[\x00-\x08\x0b-\x1f]", " ", str(value or "")).strip()
    return value[:limit]


def save_enquiry(args, ip, channel):
    name = clean(args.get("name"), 120)
    email = clean(args.get("email"), 200)
    organisation = clean(args.get("organisation"), 200)
    summary = clean(args.get("summary"), 4000)
    if not name or not summary:
        raise EnquiryError("name and summary are required")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise EnquiryError("a valid email is required so PRA can reply")
    now = time.time()
    with _lock:
        recent = [t for t in _hits.get(ip, []) if now - t < RATE_WINDOW]
        if len(recent) >= RATE_LIMIT:
            raise EnquiryError("too many enquiries from this address, please email enquiries@pacificriskadvisors.com")
        if ENQUIRIES.exists() and ENQUIRIES.stat().st_size > MAX_ENQUIRY_FILE:
            raise EnquiryError("the enquiry inbox is full, please email enquiries@pacificriskadvisors.com")
        recent.append(now)
        _hits[ip] = recent
        ref = "ENQ-" + time.strftime("%y%m%d", time.gmtime(now)) + "-" + format(int(now * 1000) % 0xFFFFF, "05X")
        record = {
            "ref": ref, "received": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
            "channel": channel, "name": name, "email": email, "organisation": organisation,
            "countries": clean(args.get("countries"), 300), "standard": clean(args.get("standard"), 300),
            "timetable": clean(args.get("timetable"), 300), "summary": summary,
            "via_agent": clean(args.get("via_agent"), 120), "ip": ip,
        }
        ENQUIRIES.parent.mkdir(parents=True, exist_ok=True)
        with ENQUIRIES.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return ref


# ---------------------------------------------------------------- tools

def obj(properties=None, required=None):
    return {"type": "object", "properties": properties or {}, "required": required or [],
            "additionalProperties": False}


READ = {"readOnlyHint": True, "openWorldHint": False}

TOOLS = [
    {"name": "get_firm_overview", "title": "Firm overview",
     "description": "Who Pacific Risk Advisors is: summary, vision, values, why PRA, headquarters and contact details.",
     "inputSchema": obj(), "annotations": READ},
    {"name": "list_capabilities", "title": "List services",
     "description": "PRA's services, each with an id and a short description.",
     "inputSchema": obj(), "annotations": READ},
    {"name": "list_audiences", "title": "Who PRA works with",
     "description": "The three groups PRA works with (financial sector, multinationals, local and regional corporates) and what PRA does for each.",
     "inputSchema": obj(), "annotations": READ},
    {"name": "get_capability", "title": "Capability detail",
     "description": "Full detail of one capability by id, as returned by list_capabilities.",
     "inputSchema": obj({"id": {"type": "string"}}, ["id"]), "annotations": READ},
    {"name": "list_standards", "title": "Standards",
     "description": "The international standards and frameworks PRA tracks and works to.",
     "inputSchema": obj(), "annotations": READ},
    {"name": "get_coverage", "title": "Coverage",
     "description": "PRA's reach: Inogen Alliance coverage and countries where PRA has its own advisors. Pass a country to check one.",
     "inputSchema": obj({"country": {"type": "string"}}), "annotations": READ},
    {"name": "get_operating_model", "title": "How PRA uses AI agents",
     "description": "How PRA divides work between software agents and human advisors, and the safeguards on client data and sign-off.",
     "inputSchema": obj(), "annotations": READ},
    {"name": "search_knowledge", "title": "Search PRA's public knowledge",
     "description": "Free-text search across PRA's published answers, capabilities and coverage. Returns the best matches.",
     "inputSchema": obj({"query": {"type": "string"}}, ["query"]), "annotations": READ},
    {"name": "submit_enquiry", "title": "Send an enquiry to PRA",
     "description": "Send a brief to PRA on behalf of a person. A PRA advisor reads it and replies by email. "
                    "Only call this when the person has asked you to contact PRA. Do not include confidential documents.",
     "inputSchema": obj({
         "name": {"type": "string", "description": "The person PRA should reply to"},
         "email": {"type": "string"},
         "organisation": {"type": "string"},
         "summary": {"type": "string", "description": "The target or portfolio and what is needed"},
         "countries": {"type": "string"},
         "standard": {"type": "string", "description": "Standard to be met, for example IFC Performance Standards"},
         "timetable": {"type": "string"},
         "via_agent": {"type": "string", "description": "Name of the assistant sending this"},
     }, ["name", "email", "summary"]),
     "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}},
]


def call_tool(name, args, ip):
    k = knowledge()
    if name == "get_firm_overview":
        return k["firm"]
    if name == "list_capabilities":
        return {"services": [{"id": c["id"], "name": c["name"], "summary": c["summary"]} for c in k["capabilities"]]}
    if name == "list_audiences":
        return {"audiences": k["audiences"]}
    if name == "get_capability":
        for c in k["capabilities"]:
            if c["id"] == args.get("id"):
                return c
        raise ValueError("unknown capability id, call list_capabilities for valid ids")
    if name == "list_standards":
        return {"standards": k["standards"]}
    if name == "get_coverage":
        total = sum(len(r["countries"]) for r in k["coverage"])
        country = clean(args.get("country"), 80).lower()
        if country:
            for r in k["coverage"]:
                for c in r["countries"]:
                    if c.lower() == country:
                        return {"country": c, "region": r["region"], "has_advisors": True}
            return {"country": args.get("country"), "has_advisors": False,
                    "note": "No PRA advisor is listed there. Through the Inogen Alliance PRA covers more than 150 countries, ask via submit_enquiry."}
        return {"reach": k["reach"], "countries_with_pra_advisors": total, "regions": k["coverage"],
                "headquarters": k["firm"]["headquarters"]}
    if name == "get_operating_model":
        return k["operating_model"]
    if name == "search_knowledge":
        query = clean(args.get("query"), 500)
        if not query:
            raise ValueError("query is required")
        results = search(query)
        return {"query": query, "results": results,
                "note": None if results else "No published answer matched. Use submit_enquiry to put the question to an advisor."}
    if name == "submit_enquiry":
        ref = save_enquiry(args, ip, "mcp")
        return {"reference": ref, "status": "received",
                "next": "A PRA advisor will read this and reply by email. Nothing is sent automatically."}
    raise KeyError(name)


# ---------------------------------------------------------------- JSON-RPC

def rpc_error(rid, code, message):
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def handle_rpc(msg, ip):
    """Return a response dict, or None for notifications."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or "method" not in msg:
        return rpc_error(msg.get("id") if isinstance(msg, dict) else None, -32600, "Invalid Request")
    method, rid, params = msg["method"], msg.get("id"), msg.get("params") or {}
    if "id" not in msg:
        return None
    if method == "initialize":
        asked = params.get("protocolVersion")
        version = asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": version, "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO, "instructions": INSTRUCTIONS}}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name, args = params.get("name"), params.get("arguments") or {}
        if not isinstance(args, dict):
            return rpc_error(rid, -32602, "arguments must be an object")
        try:
            data = call_tool(name, args, ip)
        except KeyError:
            return rpc_error(rid, -32602, f"Unknown tool: {name}")
        except (ValueError, EnquiryError) as exc:
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text", "text": str(exc)}], "isError": True}}
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, indent=2)}],
            "structuredContent": data, "isError": False}}
    return rpc_error(rid, -32601, f"Method not found: {method}")


# ---------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    server_version = "pra-mcp/0.1"
    protocol_version = "HTTP/1.1"
    static_root = None

    def log_message(self, fmt, *args):
        print(f"{self.client_ip()} {fmt % args}", flush=True)

    def client_ip(self):
        fwd = self.headers.get("X-Forwarded-For", "") if self.client_address[0] == "127.0.0.1" else ""
        return (fwd.split(",")[0].strip() or self.client_address[0])[:64]

    def send_json(self, status, payload, extra=None):
        body = b"" if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        if body:
            self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        origin = self.headers.get("Origin")
        if origin:  # public, unauthenticated, read-mostly: any origin may call it
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Expose-Headers", "Mcp-Session-Id")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY:
            self.send_json(413, {"error": "body too large"})
            return None
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return ...

    def do_OPTIONS(self):
        self.send_json(204, None, {
            "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Accept, Authorization, Mcp-Session-Id, MCP-Protocol-Version, Last-Event-ID",
            "Access-Control-Max-Age": "86400"})

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/")
        if path == "/mcp":
            msg = self.read_json()
            if msg is None:
                return
            if msg is ...:
                return self.send_json(400, rpc_error(None, -32700, "Parse error"))
            if isinstance(msg, list):
                replies = [r for r in (handle_rpc(m, self.client_ip()) for m in msg[:20]) if r is not None]
                return self.send_json(200, replies) if replies else self.send_json(202, None)
            reply = handle_rpc(msg, self.client_ip())
            return self.send_json(202, None) if reply is None else self.send_json(200, reply)
        if path == "/api/enquiry":
            msg = self.read_json()
            if msg is None:
                return
            if not isinstance(msg, dict):
                return self.send_json(400, {"error": "expected a JSON object"})
            if msg.get("website"):  # honeypot field, filled only by bots
                return self.send_json(200, {"reference": "ENQ-000000-00000"})
            try:
                return self.send_json(200, {"reference": save_enquiry(msg, self.client_ip(), "web")})
            except EnquiryError as exc:
                return self.send_json(422, {"error": str(exc)})
        self.send_json(404, {"error": "not found"})

    def do_GET(self):
        path = self.path.split("?")[0]
        if path.rstrip("/") == "/mcp":  # no server-initiated stream is offered
            return self.send_json(405, rpc_error(None, -32000, "Use POST. This server does not offer an SSE stream."),
                                  {"Allow": "POST, OPTIONS"})
        if path == "/healthz":
            return self.send_json(200, {"ok": True, "knowledge": knowledge()["version"]})
        if self.static_root:
            return self.serve_static(path)
        self.send_json(404, {"error": "not found"})

    def do_DELETE(self):
        self.send_json(405, None, {"Allow": "POST, OPTIONS"})

    def serve_static(self, path):
        rel = path.lstrip("/") or "index.html"
        target = (self.static_root / rel).resolve()
        if target.is_dir():
            target = target / "index.html"
        if self.static_root not in target.parents or not target.is_file():
            return self.send_json(404, {"error": "not found"})
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(str(target))[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--host", default=os.environ.get("PRA_MCP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PRA_MCP_PORT", "8791")))
    parser.add_argument("--static", help="also serve this directory (local preview only)")
    args = parser.parse_args()
    if args.static:
        Handler.static_root = Path(args.static).resolve()
    knowledge()
    print(f"pra-mcp listening on http://{args.host}:{args.port}/mcp", flush=True)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
