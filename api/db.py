"""DuckDB access for Spark/Hail-exported gnomAD browser Parquet (dotted column names)."""
from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import duckdb

DEFAULT_PARQUET_ROOT = Path("/data/agent/gnomad/data")

# Preferred response fields → possible Parquet column names (Spark-flattened)
FIELD_CANDIDATES: dict[str, tuple[str, ...]] = {
    "chrom": ("locus.contig",),
    "pos": ("locus.position",),
    "alleles": ("alleles",),
    "variant_id": ("variant_id",),
    "rsids": ("rsids",),
    "caid": ("caid",),
    "cadd_phred": ("in_silico_predictors.cadd.phred",),
    "revel_max": ("in_silico_predictors.revel_max",),
    "spliceai_ds_max": ("in_silico_predictors.spliceai_ds_max",),
    "joint_ac": ("joint.freq.all.ac",),
    "joint_an": ("joint.freq.all.an",),
    "joint_hom": ("joint.freq.all.homozygote_count",),
    "joint_faf95_max": ("joint.fafmax.faf95_max",),
    "joint_faf95_anc": ("joint.fafmax.faf95_max_gen_anc",),
    "joint_grpmax_af": ("joint.grpmax.AF",),
    "joint_grpmax_anc": ("joint.grpmax.gen_anc",),
    "exome_ac": ("exome.freq.all.ac",),
    "exome_an": ("exome.freq.all.an",),
    "exome_hom": ("exome.freq.all.homozygote_count",),
    "genome_ac": ("genome.freq.all.ac",),
    "genome_an": ("genome.freq.all.an",),
    "genome_hom": ("genome.freq.all.homozygote_count",),
}


def parquet_root() -> Path:
    return Path(os.environ.get("GNOMAD_PARQUET_ROOT", DEFAULT_PARQUET_ROOT)).expanduser()


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("SET threads TO 4")
    return con


def list_chroms(root: Optional[Path] = None) -> list[str]:
    root = root or parquet_root()
    if not root.is_dir():
        return []
    chroms = []
    for p in sorted(root.iterdir()):
        if p.is_dir() and p.name.startswith("chrom="):
            chroms.append(p.name.split("=", 1)[1])
    return chroms


def normalize_chrom(chrom: str) -> str:
    c = chrom.strip()
    if c.lower().startswith("chr"):
        c = c[3:]
    return c.upper() if c.upper() in ("X", "Y", "M", "MT") else c


def chrom_glob(chrom: str, root: Optional[Path] = None) -> str:
    root = root or parquet_root()
    c = normalize_chrom(chrom)
    part = root / f"chrom={c}"
    if not part.is_dir():
        raise FileNotFoundError(f"Missing partition: {part} (have: {list_chroms(root)})")
    return str(part / "**" / "*.parquet")


@lru_cache(maxsize=32)
def _columns_for_glob(glob: str) -> frozenset[str]:
    con = connect()
    rows = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{glob}')").fetchall()
    # rows: (column_name, column_type, ...)
    return frozenset(r[0] for r in rows)


def _select_sql(glob: str) -> str:
    available = _columns_for_glob(glob)
    parts = []
    for alias, candidates in FIELD_CANDIDATES.items():
        col = next((c for c in candidates if c in available), None)
        if col is None:
            parts.append(f"NULL AS {alias}")
        elif "." in col:
            parts.append(f'"{col}" AS {alias}')
        else:
            parts.append(f"{col} AS {alias}")
    return ",\n  ".join(parts)


_VARIANT_ID_RE = re.compile(
    r"^(?:chr)?(\d+|X|Y|MT|M)-(\d+)-([ACGTN]+)-([ACGTN]+)$", re.I
)


def parse_query(q: str) -> dict[str, Any]:
    q = q.strip()
    low = q.lower()
    if low.startswith("rs") and low[2:].isdigit():
        return {"type": "rsid", "rsid": low}

    m = _VARIANT_ID_RE.match(q)
    if m:
        chrom = normalize_chrom(m.group(1))
        pos = int(m.group(2))
        ref, alt = m.group(3).upper(), m.group(4).upper()
        return {
            "type": "variant_id",
            "variant_id": f"{chrom}-{pos}-{ref}-{alt}",
            "chrom": chrom,
            "pos": pos,
        }

    if ":" in q:
        parts = q.replace("CHR", "chr").split(":")
        chrom_raw = parts[0]
        if chrom_raw.lower().startswith("chr"):
            chrom_raw = chrom_raw[3:]
        chrom = normalize_chrom(chrom_raw)
        pos = int(parts[1])
        if len(parts) >= 4:
            ref, alt = parts[2].upper(), parts[3].upper()
            return {
                "type": "variant_id",
                "variant_id": f"{chrom}-{pos}-{ref}-{alt}",
                "chrom": chrom,
                "pos": pos,
            }
        return {"type": "locus", "chrom": chrom, "pos": pos}

    raise ValueError(f"Unrecognized query: {q!r} (rsID | Y-pos-ref-alt | Y:pos)")


def _af(ac: Any, an: Any) -> Optional[float]:
    if ac is None or an is None or an == 0:
        return None
    return float(ac) / float(an)


def row_to_dict(row: tuple, columns: list[str]) -> dict[str, Any]:
    d = dict(zip(columns, row))
    for k in ("rsids", "alleles"):
        v = d.get(k)
        if v is None:
            d[k] = []
        elif isinstance(v, (list, tuple)):
            d[k] = list(v)
        else:
            d[k] = [v]
    d["joint_af"] = _af(d.get("joint_ac"), d.get("joint_an"))
    d["exome_af"] = _af(d.get("exome_ac"), d.get("exome_an"))
    d["genome_af"] = _af(d.get("genome_ac"), d.get("genome_an"))
    return d


def _fetch(con: duckdb.DuckDBPyConnection, sql: str, params: Optional[list[Any]] = None) -> list[dict[str, Any]]:
    cur = con.execute(sql, params or [])
    cols = [c[0] for c in cur.description]
    return [row_to_dict(r, cols) for r in cur.fetchall()]


def lookup_variant(q: str, root: Optional[Path] = None) -> list[dict[str, Any]]:
    spec = parse_query(q)
    con = connect()
    root = root or parquet_root()

    if spec["type"] == "rsid":
        chroms = list_chroms(root)
        if not chroms:
            raise FileNotFoundError(f"No chrom=* under {root}")
        unions = []
        params: list[Any] = []
        for c in chroms:
            g = chrom_glob(c, root)
            sel = _select_sql(g)
            unions.append(f"SELECT {sel} FROM read_parquet(?)")
            params.append(g)
        inner = " UNION ALL ".join(f"({u})" for u in unions)
        sql = f"SELECT * FROM ({inner}) t WHERE list_contains(rsids, ?) LIMIT 20"
        params.append(spec["rsid"])
        return _fetch(con, sql, params)

    chrom = spec["chrom"]
    glob = chrom_glob(chrom, root)
    sel = _select_sql(glob)

    if spec["type"] == "variant_id":
        vid = spec["variant_id"]
        sql = f"""
          SELECT {sel}
          FROM read_parquet(?)
          WHERE variant_id = ? OR variant_id = ?
          LIMIT 20
        """
        return _fetch(con, sql, [glob, vid, f"chr{vid}"])

    sql = f"""
      SELECT {sel}
      FROM read_parquet(?)
      WHERE "locus.position" = ?
      LIMIT 50
    """
    return _fetch(con, sql, [glob, spec["pos"]])


def locus_query(
    chrom: str,
    pos: int,
    window_bp: int = 50_000,
    limit: int = 50,
    root: Optional[Path] = None,
) -> list[dict[str, Any]]:
    glob = chrom_glob(chrom, root)
    sel = _select_sql(glob)
    start = max(0, pos - window_bp)
    end = pos + window_bp
    con = connect()
    sql = f"""
      SELECT {sel}
      FROM read_parquet(?)
      WHERE "locus.position" BETWEEN ? AND ?
      ORDER BY "locus.position", variant_id
      LIMIT ?
    """
    return _fetch(con, sql, [glob, start, end, limit])


def health(root: Optional[Path] = None) -> dict[str, Any]:
    root = root or parquet_root()
    chroms = list_chroms(root)
    ok = root.is_dir() and bool(chroms)
    n = None
    err = None
    if ok and "Y" in chroms:
        try:
            con = connect()
            g = chrom_glob("Y", root)
            n = con.execute("SELECT COUNT(*) FROM read_parquet(?)", [g]).fetchone()[0]
        except Exception as exc:  # noqa: BLE001
            ok = False
            err = str(exc)
    out: dict[str, Any] = {
        "ok": ok,
        "parquet_root": str(root),
        "chroms": chroms,
        "chrY_variants": n,
        "dataset": "gnomAD browser v4.1.1 (local parquet)",
    }
    if err:
        out["error"] = err
    return out
