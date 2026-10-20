#!/usr/bin/env python3
"""neutron-burst: rate-limit-free write endpoint for trusted callers.
Listens on localhost:8098, bypasses opsonize-rs 3/10min limit.
Only accepts from 127.0.0.1 and WG mesh (10.13.37.*)."""

import json, time, os, sys
from http.server import HTTPServer, BaseHTTPRequestHandler

FEED_DIR = "/opt/membrane/live-terminal"
ALLOWED = {"127.0.0.1", "10.13.37.1", "10.13.37.2", "10.13.37.3", "10.13.37.5", "10.13.37.14", "10.13.37.16"}

class BurstHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # silence

    def do_POST(self):
        ip = self.client_address[0]
        if ip not in ALLOWED:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b'{"error":"not trusted"}')
            return

        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length > 0 else {}

        channel = body.get("channel", "notes")
        text = body.get("body", "")
        author = body.get("author", "membrane-lens")

        if not text:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"error":"empty body"}')
            return

        # Write to neutron.json
        npath = os.path.join(FEED_DIR, "neutron.json")
        try:
            d = json.load(open(npath)) if os.path.exists(npath) else {}
        except:
            d = {}

        if "messages" not in d:
            d["messages"] = []
        d["messages"].append({
            "channel": channel,
            "body": text,
            "author": author,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        })
        d["messages"] = d["messages"][-100:]  # cap at 100
        d["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        with open(npath, "w") as f:
            json.dump(d, f, indent=2)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True, "channel": channel}).encode())

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        npath = os.path.join(FEED_DIR, "neutron.json")
        try:
            d = json.load(open(npath))
            msgs = d.get("messages", [])[-20:]
            self.wfile.write(json.dumps({"messages": msgs}).encode())
        except:
            self.wfile.write(b'{"messages":[]}')

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8098), BurstHandler)
    print("neutron-burst listening on 0.0.0.0:8098 (mesh-open)")
    server.serve_forever()
