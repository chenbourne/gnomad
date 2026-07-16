#!/usr/bin/env python3
"""
gnomAD local Parquet API (DuckDB).

Data layout (Hive partitions from Spark):
  $GNOMAD_PARQUET_ROOT/chrom=9/part-*.snappy.parquet
  $GNOMAD_PARQUET_ROOT/chrom=Y/part-*.snappy.parquet
  default root: /data/agent/gnomad/data

Run on the machine that has the parquet:
  python3 -m venv .venv && source .venv/bin/activate
  pip install -r api/requirements.txt
  # optional: export GNOMAD_PARQUET_ROOT=/data/agent/gnomad/data
  uvicorn api.app:app --host 0.0.0.0 --port 8923
  # or: bash api/start.sh

Examples:
  curl http://127.0.0.1:8923/health
  curl 'http://127.0.0.1:8923/variant?q=Y:2781489'
  curl 'http://127.0.0.1:8923/locus?chrom=Y&pos=2781489&window_kb=10'
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse

from api.constraint import gene_constraint
from api.db import (
    batch_lookup,
    gene_variants,
    health,
    list_chroms,
    locus_query,
    lookup_variant,
    parquet_root,
    schema_for_chrom,
)

# Prefer GNOMAD_WEB_DIR; else <repo>/web next to api/
_REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = Path(
    os.environ.get("GNOMAD_WEB_DIR", str(_REPO_ROOT / "web"))
).expanduser().resolve()

_UI_ASSETS = {
    "index.html": "text/html; charset=utf-8",
    "app.js": "application/javascript; charset=utf-8",
    "styles.css": "text/css; charset=utf-8",
}

app = FastAPI(
    title="gnomAD local API",
    description="Query Hail/Spark-exported gnomAD browser Parquet via DuckDB",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("GNOMAD_API_CORS", "*").split(","),
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def api_health() -> dict[str, Any]:
    h = health()
    h["web_dir"] = str(WEB_DIR)
    h["web_present"] = (WEB_DIR / "index.html").is_file()
    return h


@app.get("/chroms")
def api_chroms() -> dict[str, Any]:
    root = parquet_root()
    return {"parquet_root": str(root), "chroms": list_chroms(root)}


@app.get("/schema")
def api_schema(chrom: str = Query("Y", description="chrom partition to describe")) -> dict[str, Any]:
    try:
        return schema_for_chrom(chrom)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/variant")
def api_variant(q: str = Query(..., description="rsID | 9-123-A-G | chr9:123")) -> dict[str, Any]:
    try:
        result = lookup_variant(q)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"query failed: {exc}") from exc

    hits = result.get("variants") or []
    if not hits:
        # gnomAD-style: absent site → 404 with clear message (+ optional locus hint)
        raise HTTPException(
            status_code=404,
            detail={
                "message": result.get("message") or f"Variant not found: {q}",
                "query": q,
                "chrom": result.get("chrom"),
                "pos": result.get("pos"),
                "suggest_locus": bool(result.get("pos") is not None and result.get("chrom")),
            },
        )
    return {
        "ok": True,
        "query": q,
        "exact": True,
        "n_hits": len(hits),
        "variants": hits,
    }


@app.get("/locus")
def api_locus(
    chrom: str = Query(..., description="9, Y, chr9, chrY, …"),
    pos: int = Query(..., description="center position (bp)"),
    window_kb: float = Query(50.0, description="half-window in kb"),
    limit: int = Query(50, ge=1, le=500),
) -> dict[str, Any]:
    try:
        hits = locus_query(chrom, pos, window_bp=int(window_kb * 1000), limit=limit)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"query failed: {exc}") from exc
    return {
        "ok": True,
        "chrom": chrom,
        "pos": pos,
        "window_kb": window_kb,
        "n_hits": len(hits),
        "variants": hits,
    }


@app.get("/batch")
def api_batch(
    rsids: str = Query(..., description="Comma-separated rsIDs, max 20"),
) -> dict[str, Any]:
    ids = [x.strip() for x in rsids.replace(";", ",").split(",") if x.strip()]
    if len(ids) > 20:
        raise HTTPException(status_code=400, detail="max 20 rsIDs per batch")
    try:
        rows = batch_lookup(ids)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "n": len(rows), "records": rows}


@app.get("/gene")
def api_gene(
    gene: str = Query(..., description="Gene symbol, e.g. SRY"),
    mode: str = Query(
        "all",
        description="all | rare | common | lof | missense",
        pattern="^(all|rare|common|lof|missense)$",
    ),
    chrom: Optional[str] = Query(None, description="Limit to chrom partition (e.g. 9, Y)"),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    try:
        result = gene_variants(gene, mode=mode, chrom=chrom, limit=limit)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"query failed: {exc}") from exc
    return {"ok": True, **result}


@app.get("/constraint")
def api_constraint(gene: str = Query(..., description="Gene symbol")) -> dict[str, Any]:
    result = gene_constraint(gene)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("message") or "not found")
    return result


@app.get("/api")
def api_info() -> dict[str, Any]:
    return {
        "service": "gnomAD local API",
        "ui": "/ui/",
        "docs": "/docs",
        "health": "/health",
        "variant": "/variant?q=9:22125515",
        "locus": "/locus?chrom=9&pos=22125515&window_kb=10",
        "batch": "/batch?rsids=rs1,rs2",
        "gene": "/gene?gene=ABO&mode=rare&chrom=9",
        "constraint": "/constraint?gene=BRCA1",
        "parquet_root": str(parquet_root()),
        "web_dir": str(WEB_DIR),
        "web_present": (WEB_DIR / "index.html").is_file(),
    }


def _ui_file(name: str) -> FileResponse:
    if name not in _UI_ASSETS:
        raise HTTPException(status_code=404, detail=f"Unknown UI asset: {name}")
    path = WEB_DIR / name
    if not path.is_file():
        raise HTTPException(
            status_code=503,
            detail=(
                f"Web UI missing: {path}. "
                "On the server run: ls web/ && git pull "
                "(need web/index.html, web/app.js, web/styles.css). "
                "Or: export GNOMAD_WEB_DIR=/path/to/web"
            ),
        )
    return FileResponse(path, media_type=_UI_ASSETS[name])


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/ui/")


@app.get("/ui")
@app.get("/ui/")
def ui_index() -> FileResponse:
    return _ui_file("index.html")


@app.get("/ui/{asset}")
def ui_asset(asset: str) -> FileResponse:
    return _ui_file(asset)
