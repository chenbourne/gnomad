#!/usr/bin/env python3
"""
gnomAD local Parquet API (DuckDB).

Data layout (Hive partitions from Spark):
  $GNOMAD_PARQUET_ROOT/chrom=Y/part-*.snappy.parquet
  default root: /data/agent/gnomad/data

Run on the machine that has the parquet:
  python3 -m venv .venv && source .venv/bin/activate
  pip install -r api/requirements.txt
  # optional: export GNOMAD_PARQUET_ROOT=/data/agent/gnomad/data
  uvicorn api.app:app --host 0.0.0.0 --port 8088
  # or: bash api/start.sh

Examples:
  curl http://127.0.0.1:8088/health
  curl 'http://127.0.0.1:8088/variant?q=Y:2781489'
  curl 'http://127.0.0.1:8088/locus?chrom=Y&pos=2781489&window_kb=10'
"""
from __future__ import annotations

import os
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from api.db import health, list_chroms, locus_query, lookup_variant, parquet_root

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
    return health()


@app.get("/chroms")
def api_chroms() -> dict[str, Any]:
    root = parquet_root()
    return {"parquet_root": str(root), "chroms": list_chroms(root)}


@app.get("/variant")
def api_variant(q: str = Query(..., description="rsID | Y-2781489-C-T | Y:2781489")) -> dict[str, Any]:
    try:
        hits = lookup_variant(q)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"query failed: {exc}") from exc
    if not hits:
        raise HTTPException(status_code=404, detail=f"not found: {q}")
    return {"ok": True, "query": q, "n_hits": len(hits), "variants": hits}


@app.get("/locus")
def api_locus(
    chrom: str = Query(..., description="Y or chrY"),
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


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "service": "gnomAD local API",
        "docs": "/docs",
        "health": "/health",
        "variant": "/variant?q=Y:2781489",
        "locus": "/locus?chrom=Y&pos=2781489&window_kb=10",
        "parquet_root": str(parquet_root()),
    }
