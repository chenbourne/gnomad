"""Optional gnomAD gene constraint metrics (separate from sites Parquet)."""
from __future__ import annotations

import csv
import gzip
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional, TextIO

REPO_ROOT = Path(__file__).resolve().parents[1]
# Prefer env, then server deploy path, then file checked into repo root.
_CANDIDATES = (
    Path("/data/agent/gnomad/data/gnomad.v4.1.constraint_metrics.tsv"),
    Path("/data/agent/gnomad/data/gnomad.v4.1.constraint_metrics.tsv.gz"),
    REPO_ROOT / "gnomad.v4.1.constraint_metrics.tsv",
    REPO_ROOT / "gnomad.v4.1.constraint_metrics.tsv.gz",
)


def constraint_path() -> Path:
    env = os.environ.get("GNOMAD_CONSTRAINT_TSV")
    if env:
        return Path(env).expanduser()
    for path in _CANDIDATES:
        if path.is_file():
            return path
    return _CANDIDATES[0]


def _open_text(path: Path) -> TextIO:
    if path.suffix == ".gz" or path.name.endswith(".tsv.gz"):
        return gzip.open(path, "rt", newline="")  # type: ignore[return-value]
    return path.open("r", newline="")


def _is_preferred(row: dict[str, str], existing: Optional[dict[str, Any]]) -> bool:
    """Prefer MANE Select / canonical transcript rows when multiple exist."""
    if existing is None:
        return True
    mane = (row.get("mane_select") or "").strip().lower()
    if mane in {"true", "1", "yes"}:
        return True
    can = (row.get("canonical") or "").strip().lower()
    if can in {"true", "1", "yes"} and not existing.get("_mane"):
        return True
    return False


@lru_cache(maxsize=1)
def _load_constraint() -> dict[str, dict[str, Any]]:
    path = constraint_path()
    if not path.is_file():
        return {}
    by_gene: dict[str, dict[str, Any]] = {}
    with _open_text(path) as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            gene = (row.get("gene") or row.get("gene_symbol") or "").strip()
            if not gene:
                continue
            key = gene.upper()
            existing = by_gene.get(key)
            if not _is_preferred(row, existing):
                continue
            mane = (row.get("mane_select") or "").strip().lower() in {"true", "1", "yes"}
            by_gene[key] = {
                "gene": gene,
                "transcript": row.get("transcript") or row.get("canonical_transcript"),
                "pLI": _float(row.get("lof.pLI") or row.get("pLI")),
                "LOEUF": _float(row.get("lof.oe_ci.upper") or row.get("oe_lof_upper") or row.get("LOEUF")),
                "oe_lof": _float(row.get("lof.oe") or row.get("oe_lof")),
                "oe_mis": _float(row.get("mis.oe") or row.get("oe_mis")),
                "lof_z": _float(row.get("lof.z_score") or row.get("lof_z")),
                "mis_z": _float(row.get("mis.z_score") or row.get("mis_z")),
                "_mane": mane,
            }
    for row in by_gene.values():
        row.pop("_mane", None)
    return by_gene


def _float(v: Any) -> Optional[float]:
    if v is None or v == "" or v == "NA":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def gene_constraint(gene: str) -> dict[str, Any]:
    gene_u = gene.strip().upper()
    table = _load_constraint()
    path = constraint_path()
    if not table:
        return {
            "ok": False,
            "gene": gene,
            "message": (
                f"Constraint file not found at {path}. "
                "Place gnomad.v4.1.constraint_metrics.tsv(.gz) under the repo "
                "or /data/agent/gnomad/data/ (or set GNOMAD_CONSTRAINT_TSV)."
            ),
        }
    row = table.get(gene_u)
    if not row:
        return {"ok": False, "gene": gene, "message": f"No constraint row for {gene}"}
    pli = row.get("pLI")
    loeuf = row.get("LOEUF")
    if pli is not None and pli > 0.9:
        interp = "高 pLI，基因对 LoF 变异不耐受，LoF 更可能致病"
    elif loeuf is not None and loeuf < 0.35:
        interp = "低 LOEUF，基因高度约束"
    else:
        interp = "约束指标未达典型高约束阈值，需结合具体变异判断"
    return {
        "ok": True,
        "gene": row["gene"],
        "constraint": row,
        "interpretation": interp,
        "source": str(path),
    }
