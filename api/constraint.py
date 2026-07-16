"""Optional gnomAD gene constraint metrics (separate from sites Parquet)."""
from __future__ import annotations

import csv
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

# Place official constraint TSV here, or set GNOMAD_CONSTRAINT_TSV
DEFAULT_CONSTRAINT = Path("/data/agent/gnomad/data/gnomad.v4.1.constraint_metrics.tsv")


def constraint_path() -> Path:
    return Path(os.environ.get("GNOMAD_CONSTRAINT_TSV", DEFAULT_CONSTRAINT)).expanduser()


@lru_cache(maxsize=1)
def _load_constraint() -> dict[str, dict[str, Any]]:
    path = constraint_path()
    if not path.is_file():
        return {}
    by_gene: dict[str, dict[str, Any]] = {}
    with path.open("r", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            gene = (row.get("gene") or row.get("gene_symbol") or "").strip()
            if not gene:
                continue
            # Prefer canonical transcript row when flagged
            by_gene[gene.upper()] = {
                "gene": gene,
                "transcript": row.get("transcript") or row.get("canonical_transcript"),
                "pLI": _float(row.get("lof.pLI") or row.get("pLI")),
                "LOEUF": _float(row.get("lof.oe_ci.upper") or row.get("oe_lof_upper") or row.get("LOEUF")),
                "oe_lof": _float(row.get("lof.oe") or row.get("oe_lof")),
                "oe_mis": _float(row.get("mis.oe") or row.get("oe_mis")),
                "lof_z": _float(row.get("lof.z_score") or row.get("lof_z")),
                "mis_z": _float(row.get("mis.z_score") or row.get("mis_z")),
            }
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
    if not table:
        return {
            "ok": False,
            "gene": gene,
            "message": (
                f"Constraint file not found at {constraint_path()}. "
                "Download gnomAD v4.1 constraint_metrics.tsv to that path "
                "(or set GNOMAD_CONSTRAINT_TSV)."
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
        "source": str(constraint_path()),
    }
