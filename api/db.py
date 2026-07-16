"""DuckDB access for Spark/Hail-exported gnomAD browser Parquet (dotted column names)."""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import duckdb

from api.ancestry import af, parse_ancestry_groups
from api.interpret import LOF_CONSEQUENCES, best_af, interpret_af

DEFAULT_PARQUET_ROOT = Path("/data/agent/gnomad/data")

# Scalar fields: alias -> candidate column names (first match wins)
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
    "sift_max": ("in_silico_predictors.sift_max",),
    "polyphen_max": ("in_silico_predictors.polyphen_max",),
    "phylop": ("in_silico_predictors.phylop",),
    # joint
    "joint_ac": ("joint.freq.all.ac",),
    "joint_an": ("joint.freq.all.an",),
    "joint_hom": ("joint.freq.all.homozygote_count",),
    "joint_faf95_max": ("joint.fafmax.faf95_max",),
    "joint_faf95_anc": ("joint.fafmax.faf95_max_gen_anc",),
    "joint_faf99_max": ("joint.fafmax.faf99_max",),
    "joint_grpmax_af": ("joint.grpmax.AF",),
    "joint_grpmax_anc": ("joint.grpmax.gen_anc",),
    "joint_grpmax_ac": ("joint.grpmax.AC",),
    "joint_grpmax_an": ("joint.grpmax.AN",),
    # exome
    "exome_ac": ("exome.freq.all.ac",),
    "exome_an": ("exome.freq.all.an",),
    "exome_hom": ("exome.freq.all.homozygote_count",),
    "exome_faf95_max": (
        "exome.fafmax.gnomad.faf95_max",
        "exome.fafmax.faf95_max",
    ),
    "exome_faf95_anc": (
        "exome.fafmax.gnomad.faf95_max_gen_anc",
        "exome.fafmax.faf95_max_gen_anc",
    ),
    # genome
    "genome_ac": ("genome.freq.all.ac",),
    "genome_an": ("genome.freq.all.an",),
    "genome_hom": ("genome.freq.all.homozygote_count",),
    "genome_faf95_max": ("genome.fafmax.faf95_max",),
    "genome_faf95_anc": ("genome.fafmax.faf95_max_gen_anc",),
}

# JSON blobs via to_json() for nested arrays/structs
JSON_CANDIDATES: dict[str, tuple[str, ...]] = {
    "joint_ancestry_raw": ("joint.freq.all.ancestry_groups",),
    "exome_ancestry_raw": ("exome.freq.all.ancestry_groups",),
    "genome_ancestry_raw": ("genome.freq.all.ancestry_groups",),
    "joint_flags_raw": ("joint.flags",),
    "exome_filters_raw": ("exome.filters",),
    "genome_filters_raw": ("genome.filters",),
    "transcript_raw": ("transcript_consequences",),
}


def parquet_root() -> Path:
    return Path(os.environ.get("GNOMAD_PARQUET_ROOT", DEFAULT_PARQUET_ROOT)).expanduser()


def chrom_sort_key(chrom: str) -> tuple[int, int]:
    c = chrom.upper()
    if c in ("X", "Y"):
        return (2, 23 if c == "X" else 24)
    if c in ("M", "MT"):
        return (2, 25)
    if chrom.isdigit():
        return (1, int(chrom))
    return (3, 0)


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("SET threads TO 4")
    return con


def list_chroms(root: Optional[Path] = None) -> list[str]:
    root = root or parquet_root()
    if not root.is_dir():
        return []
    chroms = []
    for p in root.iterdir():
        if p.is_dir() and p.name.startswith("chrom="):
            chroms.append(p.name.split("=", 1)[1])
    return sorted(chroms, key=chrom_sort_key)


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
    return frozenset(r[0] for r in rows)


def schema_for_chrom(chrom: str, root: Optional[Path] = None) -> dict[str, Any]:
    glob = chrom_glob(chrom, root)
    cols = sorted(_columns_for_glob(glob))
    freq_cols = [c for c in cols if "freq" in c or "ancestry" in c]
    return {
        "chrom": normalize_chrom(chrom),
        "glob": glob,
        "n_columns": len(cols),
        "columns": cols,
        "freq_related": freq_cols[:80],
        "mapped_scalars": {k: _pick_col(cols, v) for k, v in FIELD_CANDIDATES.items()},
        "mapped_json": {k: _pick_col(cols, v) for k, v in JSON_CANDIDATES.items()},
    }


def _pick_col(available: frozenset[str] | list[str], candidates: tuple[str, ...]) -> str | None:
    avail = available if isinstance(available, frozenset) else frozenset(available)
    for c in candidates:
        if c in avail:
            return c
    return None


def _quote_col(col: str) -> str:
    return f'"{col}"' if "." in col else col


def _select_sql(glob: str) -> str:
    available = _columns_for_glob(glob)
    parts = []
    for alias, candidates in FIELD_CANDIDATES.items():
        col = _pick_col(available, candidates)
        if col is None:
            parts.append(f"NULL AS {alias}")
        else:
            parts.append(f"{_quote_col(col)} AS {alias}")
    for alias, candidates in JSON_CANDIDATES.items():
        col = _pick_col(available, candidates)
        if col is None:
            parts.append(f"NULL AS {alias}")
        else:
            parts.append(f"to_json({_quote_col(col)}) AS {alias}")
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

    raise ValueError(
        f"Unrecognized query: {q!r} (rsID | 9-123-A-G | chr9:123 | 9:123)"
    )


def _loads_json(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, (list, dict)):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return None
    return None


def _filter_display(filters: list | None, flags: list | None) -> tuple[str, str]:
    flags = flags or []
    filters = filters or []
    if flags:
        pretty = []
        for f in flags:
            if f == "discrepant_frequencies":
                pretty.append("Discrepant frequencies")
            else:
                pretty.append(str(f).replace("_", " ").capitalize())
        return ", ".join(pretty), "warning"
    if filters:
        return ", ".join(str(x) for x in filters), "fail"
    return "Pass", "pass"


def _summary_block(
    label: str,
    ac: Any,
    an: Any,
    hom: Any,
    faf95: Any,
    faf95_anc: Any,
    filters: list | None = None,
    flags: list | None = None,
    present: bool = True,
) -> dict[str, Any]:
    if not present and ac is None and an is None:
        return {
            "label": label,
            "present": False,
            "filter_display": "—",
            "filter_kind": "fail",
            "ac": None,
            "an": None,
            "af": None,
            "faf95": None,
            "homozygote_count": None,
        }
    disp, kind = _filter_display(filters, flags)
    return {
        "label": label,
        "present": True,
        "filters": filters or [],
        "flags": flags or [],
        "filter_display": disp,
        "filter_kind": kind,
        "ac": ac,
        "an": an,
        "af": af(ac, an),
        "faf95": faf95,
        "faf95_anc": faf95_anc,
        "homozygote_count": hom,
    }


def _parse_transcript(raw: Any) -> dict[str, Any]:
    tc = _loads_json(raw)
    if not isinstance(tc, list) or not tc:
        return {}
    rows = []
    for t in tc:
        if isinstance(t, dict):
            rows.append(t)
        elif hasattr(t, "_asdict"):
            rows.append(t._asdict())
    if not rows:
        return {}
    canon = [t for t in rows if t.get("is_canonical")]
    pick = canon[0] if canon else rows[0]
    genes = sorted({t.get("gene_symbol") for t in rows if t.get("gene_symbol")})
    return {
        "genes": genes,
        "primary_gene": genes[0] if genes else None,
        "consequence": pick.get("major_consequence")
        or (pick.get("consequence_terms") or [None])[0],
        "hgvsc": pick.get("hgvsc"),
        "hgvsp": pick.get("hgvsp"),
    }


def enrich_variant(d: dict[str, Any]) -> dict[str, Any]:
    """Add browser-like summary + ancestry tables."""
    for k in ("rsids", "alleles"):
        v = d.get(k)
        if v is None:
            d[k] = []
        elif not isinstance(v, list):
            d[k] = list(v) if isinstance(v, (tuple, set)) else [v]

    d["joint_af"] = af(d.get("joint_ac"), d.get("joint_an"))
    d["exome_af"] = af(d.get("exome_ac"), d.get("exome_an"))
    d["genome_af"] = af(d.get("genome_ac"), d.get("genome_an"))

    raw_chrom = d.get("chrom")
    if raw_chrom is not None:
        d["chrom"] = normalize_chrom(str(raw_chrom))

    joint_flags = _loads_json(d.pop("joint_flags_raw", None)) or []
    exome_filters = _loads_json(d.pop("exome_filters_raw", None)) or []
    genome_filters = _loads_json(d.pop("genome_filters_raw", None)) or []

    ancestry = {
        "joint": parse_ancestry_groups(_loads_json(d.pop("joint_ancestry_raw", None))),
        "exome": parse_ancestry_groups(_loads_json(d.pop("exome_ancestry_raw", None))),
        "genome": parse_ancestry_groups(_loads_json(d.pop("genome_ancestry_raw", None))),
    }
    d["ancestry"] = ancestry

    d["summary"] = {
        "exome": _summary_block(
            "Exomes",
            d.get("exome_ac"),
            d.get("exome_an"),
            d.get("exome_hom"),
            d.get("exome_faf95_max"),
            d.get("exome_faf95_anc"),
            filters=exome_filters if isinstance(exome_filters, list) else None,
            present=d.get("exome_ac") is not None or d.get("exome_an") is not None,
        ),
        "genome": _summary_block(
            "Genomes",
            d.get("genome_ac"),
            d.get("genome_an"),
            d.get("genome_hom"),
            d.get("genome_faf95_max"),
            d.get("genome_faf95_anc"),
            filters=genome_filters if isinstance(genome_filters, list) else None,
            present=d.get("genome_ac") is not None or d.get("genome_an") is not None,
        ),
        "joint": _summary_block(
            "Total",
            d.get("joint_ac"),
            d.get("joint_an"),
            d.get("joint_hom"),
            d.get("joint_faf95_max"),
            d.get("joint_faf95_anc"),
            flags=joint_flags if isinstance(joint_flags, list) else None,
            present=d.get("joint_ac") is not None or d.get("joint_an") is not None,
        ),
    }

    tx = _parse_transcript(d.pop("transcript_raw", None))
    d.update({k: v for k, v in tx.items() if v is not None})

    d["predictors"] = {
        "cadd_phred": d.get("cadd_phred"),
        "revel_max": d.get("revel_max"),
        "spliceai_ds_max": d.get("spliceai_ds_max"),
        "sift_max": d.get("sift_max"),
        "polyphen_max": d.get("polyphen_max"),
        "phylop": d.get("phylop"),
    }
    d["interpretation"] = interpret_af(best_af(d))
    return d


def row_to_dict(row: tuple, columns: list[str]) -> dict[str, Any]:
    return enrich_variant(dict(zip(columns, row)))


def _fetch(con: duckdb.DuckDBPyConnection, sql: str, params: Optional[list[Any]] = None) -> list[dict[str, Any]]:
    cur = con.execute(sql, params or [])
    cols = [c[0] for c in cur.description]
    return [row_to_dict(r, cols) for r in cur.fetchall()]


def lookup_variant(q: str, root: Optional[Path] = None) -> dict[str, Any]:
    """
    Look up by rsID / variant_id / chrom:pos (exact only, gnomAD-browser style).

    Returns dict:
      exact: True if hit(s)
      variants: list of enriched rows
      message: optional note when empty
    """
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
        hits = _fetch(con, sql, params)
        return {
            "exact": bool(hits),
            "variants": hits,
            "query": q,
            "message": None if hits else f"Variant not found for {q}",
        }

    chrom = spec["chrom"]
    glob = chrom_glob(chrom, root)
    sel = _select_sql(glob)

    if spec["type"] == "variant_id":
        vid = spec["variant_id"]
        id_candidates = {vid, f"chr{vid}"}
        placeholders = ", ".join("?" for _ in id_candidates)
        sql = f"""
          SELECT {sel}
          FROM read_parquet(?)
          WHERE variant_id IN ({placeholders})
          LIMIT 20
        """
        hits = _fetch(con, sql, [glob, *sorted(id_candidates)])
        return {
            "exact": bool(hits),
            "variants": hits,
            "query": q,
            "message": None if hits else f"Variant not found: {vid}",
        }

    # chrom:pos — exact position only (like gnomAD: a site without an alt is absent)
    sql = f"""
      SELECT {sel}
      FROM read_parquet(?)
      WHERE "locus.position" = ?
      LIMIT 50
    """
    hits = _fetch(con, sql, [glob, spec["pos"]])
    c = normalize_chrom(chrom)
    if hits:
        return {"exact": True, "variants": hits, "query": q, "pos": spec["pos"]}
    return {
        "exact": False,
        "variants": [],
        "query": q,
        "pos": spec["pos"],
        "chrom": c,
        "message": (
            f"No variant found at chr{c}:{spec['pos']}. "
            "gnomAD only includes positions with an observed alternate allele. "
            "Try a full variant ID (e.g. 9-22125515-G-C), an rsID, "
            "or browse nearby with /locus."
        ),
    }


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


def batch_lookup(rsids: list[str], root: Optional[Path] = None, max_n: int = 20) -> list[dict[str, Any]]:
    """Look up multiple rsIDs (capped)."""
    out = []
    for rsid in rsids[:max_n]:
        rsid = rsid.strip()
        if not rsid:
            continue
        if not rsid.lower().startswith("rs"):
            rsid = f"rs{rsid}"
        try:
            result = lookup_variant(rsid, root=root)
            hits = result.get("variants") or []
            out.append(
                {
                    "rsid": rsid.lower(),
                    "found": bool(hits),
                    "variant": hits[0] if hits else None,
                    "interpretation": (hits[0].get("interpretation") if hits else interpret_af(None)),
                }
            )
        except Exception as exc:  # noqa: BLE001
            out.append({"rsid": rsid, "found": False, "error": str(exc)})
    return out


def gene_variants(
    gene: str,
    mode: str = "all",
    chrom: Optional[str] = None,
    limit: int = 50,
    root: Optional[Path] = None,
) -> dict[str, Any]:
    """
    Filter sites Parquet by gene_symbol in transcript_consequences.

    mode: all | rare (AF<1% or absent) | common (AF>=1%) | lof | missense
    chrom: optional; default = all available partitions (slow if many chroms)
    """
    gene_u = gene.strip().upper()
    root = root or parquet_root()
    chroms = [normalize_chrom(chrom)] if chrom else list_chroms(root)
    if not chroms:
        raise FileNotFoundError(f"No chrom=* under {root}")

    con = connect()
    unions = []
    params: list[Any] = []
    for c in chroms:
        g = chrom_glob(c, root)
        available = _columns_for_glob(g)
        tc_col = _pick_col(
            available,
            ("transcript_consequences", "genome.vep115.transcript_consequences"),
        )
        if tc_col is None:
            continue
        sel = _select_sql(g)
        # gene match via list_transform on struct.gene_symbol
        unions.append(
            f"""
            SELECT {sel} FROM read_parquet(?)
            WHERE list_contains(
              list_transform({_quote_col(tc_col)}, x -> upper(x.gene_symbol)),
              ?
            )
            """
        )
        params.extend([g, gene_u])

    if not unions:
        return {
            "gene": gene,
            "mode": mode,
            "total_matched": 0,
            "variants": [],
            "message": "No transcript_consequences column in parquet",
        }

    inner = " UNION ALL ".join(f"({u})" for u in unions)
    # Pull a larger pool then filter in Python for mode (AF / consequence)
    sql = f"SELECT * FROM ({inner}) t LIMIT ?"
    params.append(max(limit * 20, 500))
    rows = _fetch(con, sql, params)

    def _pass(v: dict[str, Any]) -> bool:
        afv = best_af(v)
        cons = (v.get("consequence") or "") or ""
        if mode == "rare":
            return afv is None or afv < 0.01
        if mode == "common":
            return afv is not None and afv >= 0.01
        if mode == "lof":
            return cons in LOF_CONSEQUENCES
        if mode == "missense":
            return cons == "missense_variant"
        return True

    filtered = [v for v in rows if _pass(v)]
    if mode == "rare":
        filtered.sort(key=lambda v: (best_af(v) is not None, best_af(v) if best_af(v) is not None else -1))
    elif mode == "common":
        filtered.sort(key=lambda v: -(best_af(v) or 0))
    else:
        filtered.sort(key=lambda v: (v.get("pos") or 0, v.get("variant_id") or ""))

    return {
        "gene": gene,
        "mode": mode,
        "chroms_searched": chroms,
        "scanned_hits": len(rows),
        "total_matched": len(filtered),
        "returned": min(limit, len(filtered)),
        "variants": filtered[:limit],
    }


def health(root: Optional[Path] = None) -> dict[str, Any]:
    root = root or parquet_root()
    chroms = list_chroms(root)
    ok = root.is_dir() and bool(chroms)
    variant_counts: dict[str, Optional[int]] = {}
    err = None
    if ok:
        try:
            con = connect()
            for c in chroms:
                try:
                    g = chrom_glob(c, root)
                    variant_counts[c] = con.execute(
                        "SELECT COUNT(*) FROM read_parquet(?)", [g]
                    ).fetchone()[0]
                except Exception as exc:  # noqa: BLE001
                    variant_counts[c] = None
                    if err is None:
                        err = f"chr{c}: {exc}"
        except Exception as exc:  # noqa: BLE001
            ok = False
            err = str(exc)
    from api.constraint import constraint_path

    total = sum(n for n in variant_counts.values() if isinstance(n, int))
    out: dict[str, Any] = {
        "ok": ok,
        "parquet_root": str(root),
        "chroms": chroms,
        "variant_counts": variant_counts,
        "total_variants": total if variant_counts else None,
        "chrY_variants": variant_counts.get("Y"),
        "dataset": "gnomAD browser v4.1.1 (local parquet)",
        "constraint_tsv": str(constraint_path()),
        "constraint_present": constraint_path().is_file(),
        "features": [
            "summary (exome/genome/joint)",
            "ancestry tables",
            "predictors",
            "transcript (when column present)",
            "ACMG-style AF interpretation",
            "batch rsID",
            "gene filter (rare/common/lof/missense)",
            "gene constraint (if TSV present)",
        ],
    }
    if err:
        out["error"] = err
    return out
