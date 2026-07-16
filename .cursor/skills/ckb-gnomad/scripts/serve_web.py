#!/usr/bin/env python3
"""Serve API-backed web UI locally (browser fetches GNOMAD_API_BASE)."""
from __future__ import annotations

import argparse
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# scripts → skill → skills → .cursor → repo root
WEB_DIR = Path(__file__).resolve().parents[4] / "web"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8766)
    p.add_argument(
        "--api",
        default=os.environ.get("GNOMAD_API_BASE", "http://10.221.12.63:8923"),
        help="API base passed as ?api= in the printed URL",
    )
    args = p.parse_args()
    if not WEB_DIR.is_dir():
        raise SystemExit(f"Missing web dir: {WEB_DIR}")

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(WEB_DIR), **k)

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    api = args.api.rstrip("/")
    url = f"http://{args.host}:{args.port}/?q=Y:2781489&api={api}"
    print(f"web:     {WEB_DIR}", flush=True)
    print(f"api:     {api}", flush=True)
    print(f"serving: {url}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
