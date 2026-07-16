"""HTTP client for gnomAD Parquet API (stdlib urllib)."""
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# Default: deployed server; override with env GNOMAD_API_BASE or --api
DEFAULT_API_BASE = "http://10.221.12.63:8923"


def api_base(cli_value: str | None = None) -> str:
    raw = cli_value or os.environ.get("GNOMAD_API_BASE") or DEFAULT_API_BASE
    return raw.rstrip("/")


def add_api_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--api",
        default=None,
        help=f"API base URL (default: env GNOMAD_API_BASE or {DEFAULT_API_BASE})",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Force local var19.txt instead of API",
    )


def use_api(args: argparse.Namespace) -> bool:
    return not getattr(args, "local", False)


def _get(url: str, timeout: float = 60.0) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(detail)
            detail = payload.get("detail") or detail
        except json.JSONDecodeError:
            pass
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"API unreachable: {exc.reason} ({url})") from exc
    return json.loads(body)


def health(base: str | None = None) -> dict[str, Any]:
    return _get(f"{api_base(base)}/health")


def chroms(base: str | None = None) -> dict[str, Any]:
    return _get(f"{api_base(base)}/chroms")


def variant(q: str, base: str | None = None) -> dict[str, Any]:
    qs = urllib.parse.urlencode({"q": q})
    return _get(f"{api_base(base)}/variant?{qs}")


def batch(rsids: list[str], base: str | None = None) -> dict[str, Any]:
    qs = urllib.parse.urlencode({"rsids": ",".join(rsids)})
    return _get(f"{api_base(base)}/batch?{qs}")


def gene(
    gene_symbol: str,
    mode: str = "all",
    chrom: str | None = None,
    limit: int = 50,
    base: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {"gene": gene_symbol, "mode": mode, "limit": limit}
    if chrom:
        params["chrom"] = chrom
    qs = urllib.parse.urlencode(params)
    return _get(f"{api_base(base)}/gene?{qs}")


def constraint(gene_symbol: str, base: str | None = None) -> dict[str, Any]:
    qs = urllib.parse.urlencode({"gene": gene_symbol})
    return _get(f"{api_base(base)}/constraint?{qs}")


def fmt_af(af: float | None) -> str:
    if af is None:
        return "NA"
    if af == 0:
        return "0"
    if af >= 0.01:
        return f"{af:.4g}"
    return f"{af:.3e}"


def fmt_score(x: float | None, digits: int = 3) -> str:
    if x is None:
        return "NA"
    return f"{x:.{digits}g}"


def print_summary_table(summary: dict[str, Any] | None) -> None:
    if not summary:
        return
    print("--- variant summary ---")
    print(f"{'':28} {'Exomes':>12} {'Genomes':>12} {'Total':>12}")
    blocks = [summary.get("exome"), summary.get("genome"), summary.get("joint")]
    labels = ["Filters", "Allele Count", "Allele Number", "Allele Frequency", "FAF95", "Homozygotes"]
    keys = ["filter_display", "ac", "an", "af", "faf95", "homozygote_count"]
    for label, key in zip(labels, keys):
        vals = []
        for b in blocks:
            if not b or not b.get("present"):
                vals.append("—")
            elif key == "af":
                vals.append(fmt_af(b.get("af")))
            elif key == "faf95":
                vals.append(fmt_af(b.get("faf95")))
            else:
                v = b.get(key)
                vals.append(str(v) if v is not None else "—")
        print(f"{label:28} {vals[0]:>12} {vals[1]:>12} {vals[2]:>12}")


def print_ancestry_table(rows: list[dict[str, Any]], title: str) -> None:
    if not rows:
        return
    print(f"--- {title} ---")
    print(f"{'Group':<28} {'AC':>8} {'AN':>10} {'Hom':>6} {'AF':>10}")
    for r in rows:
        print(
            f"{r.get('label', r.get('id', '')):<28} "
            f"{r.get('ac') or '—':>8} "
            f"{r.get('an') or '—':>10} "
            f"{r.get('homozygote_count') or '—':>6} "
            f"{fmt_af(r.get('af')):>10}"
        )


def print_api_variant(v: dict[str, Any]) -> None:
    alleles = v.get("alleles") or []
    ref = alleles[0] if len(alleles) > 0 else "?"
    alt = alleles[1] if len(alleles) > 1 else "?"
    chrom = str(v.get("chrom") or "").removeprefix("chr")
    rsids = v.get("rsids") or []
    atype = "SNV" if len(ref) == 1 and len(alt) == 1 else "InDel"
    print(f"variant:     {atype}:{v.get('variant_id')}(GRCh38)")
    print(f"locus:       chr{chrom}:{v.get('pos')}  {ref}>{alt}")
    print(f"rsids:       {', '.join(rsids) if rsids else 'NA'}")
    print(f"caid:        {v.get('caid') or 'NA'}")
    if v.get("primary_gene") or v.get("consequence"):
        bits = [v.get("primary_gene"), v.get("consequence"), v.get("hgvsc"), v.get("hgvsp")]
        print(f"gene/cons:   {' · '.join(x for x in bits if x)}")
    pred = v.get("predictors") or {}
    print(
        f"predictors:  CADD={fmt_score(pred.get('cadd_phred') or v.get('cadd_phred'))}  "
        f"REVEL={fmt_score(pred.get('revel_max') or v.get('revel_max'))}  "
        f"SpliceAI={fmt_score(pred.get('spliceai_ds_max') or v.get('spliceai_ds_max'))}"
    )
    if v.get("interpretation"):
        print(f"interpret:   {v['interpretation']}")
    print_summary_table(v.get("summary"))
    anc = v.get("ancestry") or {}
    for slice_name, title in (
        ("joint", "ancestry AF (Total)"),
        ("exome", "ancestry AF (Exomes)"),
        ("genome", "ancestry AF (Genomes)"),
    ):
        print_ancestry_table(anc.get(slice_name) or [], title)
