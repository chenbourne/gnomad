#!/usr/bin/env python3
"""Serve a local gnomAD-style variant browser over var19.txt (or --data)."""
from __future__ import annotations

import argparse
import json
import sys
from functools import lru_cache
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from browser_payload import browser_payload, find_variants, index_list
from gnomad_io import add_data_args, load_variants, project_root, resolve_data

VIEWER_DIR = Path(__file__).resolve().parents[1] / "viewer"


class State:
    root: Path = project_root()
    data: Path | None = None


@lru_cache(maxsize=1)
def _variants():
    path = resolve_data(root=State.root, data=State.data)
    return path, load_variants(path)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(VIEWER_DIR), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            path, variants = _variants()
            return self._json(
                {"ok": True, "data": str(path), "n_variants": len(variants)}
            )
        if parsed.path == "/api/variants":
            _, variants = _variants()
            return self._json({"variants": index_list(variants)})
        if parsed.path == "/api/variant":
            qs = parse_qs(parsed.query)
            q = (qs.get("q") or qs.get("query") or [""])[0].strip()
            if not q:
                return self._json({"ok": False, "error": "missing q"}, status=400)
            _, variants = _variants()
            hits = find_variants(variants, q)
            if not hits:
                return self._json({"ok": False, "error": "not found", "query": q}, status=404)
            return self._json(
                {
                    "ok": True,
                    "query": q,
                    "n_hits": len(hits),
                    "variant": browser_payload(hits[0]),
                    "also": [browser_payload(v)["variant_id"] for v in hits[1:6]],
                }
            )
        return super().do_GET()

    def _json(self, obj: dict, status: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    add_data_args(p)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    args = p.parse_args()

    State.root = args.root or project_root()
    State.data = args.data
    if not VIEWER_DIR.is_dir():
        raise SystemExit(f"Missing viewer dir: {VIEWER_DIR}")

    path, variants = _variants()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/?q=19-44908684-T-C"
    print(f"data:     {path} ({len(variants)} variants)", flush=True)
    print(f"viewer:   {VIEWER_DIR}", flush=True)
    print(f"serving:  {url}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
