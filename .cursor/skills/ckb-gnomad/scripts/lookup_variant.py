#!/usr/bin/env python3
"""Look up a gnomAD variant via API (default) or local var19.txt (--local)."""
from __future__ import annotations

import argparse
import sys

from api_client import (
    add_api_args,
    api_base,
    print_api_variant,
    use_api,
    variant as api_variant,
)
from gnomad_io import (
    MAIN_ANC,
    Variant,
    add_data_args,
    fmt_af,
    fmt_score,
    iter_variants,
    match_rsid,
    match_variant_id,
    project_root,
    resolve_data,
)


def _parse_query(q: str) -> dict:
    q = q.strip()
    low = q.lower()
    if low.startswith("rs") and low[2:].isdigit():
        return {"rsid": q}
    if (q.count("-") >= 3 and (q[0].isdigit() or q[0].upper() in "XYM")) or q.upper().startswith(
        "CHR"
    ):
        return {"variant_id": q.removeprefix("chr").removeprefix("CHR")}
    if ":" in q:
        parts = q.replace("chr", "").replace("CHR", "").split(":")
        out: dict = {"chrom": parts[0], "pos": int(parts[1])}
        if len(parts) >= 4:
            out["ref"], out["alt"] = parts[2], parts[3]
        return out
    raise SystemExit(f"Unrecognized query: {q!r} (use rsID, variant_id, or chrom:pos[:ref:alt])")


def _match(v: Variant, spec: dict) -> bool:
    if "rsid" in spec:
        return match_rsid(v, spec["rsid"])
    if "variant_id" in spec:
        return match_variant_id(v, spec["variant_id"])
    if v.chrom != str(spec["chrom"]).removeprefix("chr").removeprefix("CHR"):
        return False
    if v.pos != spec["pos"]:
        return False
    if "ref" in spec and (v.ref != spec["ref"] or v.alt != spec["alt"]):
        return False
    return True


def _print_local(v: Variant, verbose: bool) -> None:
    print(f"variant_id:  {v.variant_id}")
    print(f"locus:       chr{v.chrom}:{v.pos}  {v.ref}>{v.alt}")
    print(f"rsids:       {', '.join(v.rsids) if v.rsids else 'NA'}")
    print(f"caid:        {v.caid or 'NA'}")
    print(f"genes:       {', '.join(v.genes) if v.genes else 'NA'}")
    print(f"consequence: {v.major_consequence or 'NA'}")
    if v.hgvsc:
        print(f"hgvsc:       {v.hgvsc}")
    if v.hgvsp:
        print(f"hgvsp:       {v.hgvsp}")
    print(
        f"joint:       AC={v.joint_ac}  AN={v.joint_an}  AF={fmt_af(v.joint_af)}  "
        f"hom={v.joint_hom}"
    )
    print(f"grpmax:      AF={fmt_af(v.grpmax_af)}  anc={v.grpmax_anc or 'NA'}")
    print(f"faf95_max:   {fmt_af(v.faf95_max)}  anc={v.faf95_max_anc or 'NA'}")
    print(
        f"predictors:  CADD={fmt_score(v.cadd_phred)}  "
        f"REVEL={fmt_score(v.revel_max)}  "
        f"SpliceAI={fmt_score(v.spliceai_ds_max)}"
    )
    ancs = [(a, v.ancestry_af[a]) for a in MAIN_ANC if a in v.ancestry_af]
    if ancs:
        print("--- ancestry AF (joint) ---")
        for aid, af in ancs:
            print(f"  {aid:10} {fmt_af(af)}")
    if verbose:
        print("--- transcript consequences ---")
        tc = v.raw.get("transcript_consequences") or []
        if isinstance(tc, list):
            for t in tc[:20]:
                if not isinstance(t, dict):
                    continue
                print(
                    f"  {t.get('gene_symbol') or '?'}\t"
                    f"{t.get('major_consequence') or ''}\t"
                    f"{t.get('hgvsc') or ''}\t{t.get('hgvsp') or ''}"
                )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    add_api_args(p)
    add_data_args(p)
    p.add_argument("query", help="rsID | variant_id | chrom:pos[:ref:alt]")
    p.add_argument("-v", "--verbose", action="store_true", help="Local mode: transcript rows")
    args = p.parse_args()

    if use_api(args):
        base = api_base(args.api)
        try:
            data = api_variant(args.query, base=base)
        except RuntimeError as exc:
            print(f"# API error ({base}): {exc}", file=sys.stderr)
            return 1
        hits = data.get("variants") or []
        print(f"# query={args.query!r}  api={base}  hits={len(hits)}")
        if not hits:
            print("No match.")
            return 1
        for i, v in enumerate(hits):
            if i:
                print("---")
            print_api_variant(v)
        return 0

    spec = _parse_query(args.query)
    path = resolve_data(root=args.root or project_root(), data=args.data)
    hits = [v for v in iter_variants(path) if _match(v, spec)]
    print(f"# query={args.query!r}  file={path.name}  hits={len(hits)}")
    if not hits:
        print("No match in local data file.")
        return 1
    for i, v in enumerate(hits):
        if i:
            print("---")
        _print_local(v, verbose=args.verbose)
    return 0


if __name__ == "__main__":
    sys.exit(main())
