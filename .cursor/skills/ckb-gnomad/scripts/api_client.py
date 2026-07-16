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


def locus(
    chrom: str,
    pos: int,
    window_kb: float = 50.0,
    limit: int = 50,
    base: str | None = None,
) -> dict[str, Any]:
    qs = urllib.parse.urlencode(
        {"chrom": chrom, "pos": pos, "window_kb": window_kb, "limit": limit}
    )
    return _get(f"{api_base(base)}/locus?{qs}")


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


def print_api_variant(v: dict[str, Any]) -> None:
    alleles = v.get("alleles") or []
    ref = alleles[0] if len(alleles) > 0 else "?"
    alt = alleles[1] if len(alleles) > 1 else "?"
    chrom = str(v.get("chrom") or "").removeprefix("chr")
    rsids = v.get("rsids") or []
    print(f"variant_id:  {v.get('variant_id')}")
    print(f"locus:       chr{chrom}:{v.get('pos')}  {ref}>{alt}")
    print(f"rsids:       {', '.join(rsids) if rsids else 'NA'}")
    print(f"caid:        {v.get('caid') or 'NA'}")
    print(
        f"joint:       AC={v.get('joint_ac')}  AN={v.get('joint_an')}  "
        f"AF={fmt_af(v.get('joint_af'))}  hom={v.get('joint_hom')}"
    )
    print(
        f"grpmax:      AF={fmt_af(v.get('joint_grpmax_af'))}  "
        f"anc={v.get('joint_grpmax_anc') or 'NA'}"
    )
    print(
        f"faf95_max:   {fmt_af(v.get('joint_faf95_max'))}  "
        f"anc={v.get('joint_faf95_anc') or 'NA'}"
    )
    print(
        f"exome:       AC={v.get('exome_ac')}  AN={v.get('exome_an')}  "
        f"AF={fmt_af(v.get('exome_af'))}  hom={v.get('exome_hom')}"
    )
    print(
        f"genome:      AC={v.get('genome_ac')}  AN={v.get('genome_an')}  "
        f"AF={fmt_af(v.get('genome_af'))}  hom={v.get('genome_hom')}"
    )
    print(
        f"predictors:  CADD={fmt_score(v.get('cadd_phred'))}  "
        f"REVEL={fmt_score(v.get('revel_max'))}  "
        f"SpliceAI={fmt_score(v.get('spliceai_ds_max'))}"
    )
