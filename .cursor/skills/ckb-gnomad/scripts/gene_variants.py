#!/usr/bin/env python3
"""List gnomAD variants for a gene (API) or local var19.txt (--local)."""
from __future__ import annotations

import argparse
import sys

from api_client import add_api_args, api_base, fmt_af, fmt_score, gene as api_gene, use_api
from gnomad_io import add_data_args, iter_variants, project_root, resolve_data


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    add_api_args(p)
    add_data_args(p)
    p.add_argument("-g", "--gene", required=True, help="Gene symbol (e.g. SRY)")
    p.add_argument(
        "--mode",
        default="all",
        choices=["all", "rare", "common", "lof", "missense"],
        help="API filter mode (default all)",
    )
    p.add_argument("--chrom", default=None, help="Limit API search to chrom (e.g. Y)")
    p.add_argument(
        "--consequence",
        default=None,
        help="Local mode only: substring filter on major_consequence",
    )
    p.add_argument("--min-af", type=float, default=None, help="Local: min joint AF")
    p.add_argument("--max-af", type=float, default=None, help="Local: max joint AF")
    p.add_argument("--top", type=int, default=50)
    args = p.parse_args()

    if use_api(args):
        base = api_base(args.api)
        try:
            data = api_gene(
                args.gene,
                mode=args.mode,
                chrom=args.chrom,
                limit=args.top,
                base=base,
            )
        except RuntimeError as exc:
            print(f"# API error ({base}): {exc}", file=sys.stderr)
            return 1
        hits = data.get("variants") or []
        print(
            f"# gene={args.gene} mode={args.mode} chroms={data.get('chroms_searched')} "
            f"matched={data.get('total_matched')} returned={len(hits)} api={base}"
        )
        print("variant_id\trsids\tconsequence\tjoint_AF\tCADD\tinterpretation")
        for v in hits:
            print(
                f"{v.get('variant_id')}\t{','.join(v.get('rsids') or []) or 'NA'}\t"
                f"{v.get('consequence') or 'NA'}\t{fmt_af(v.get('joint_af'))}\t"
                f"{fmt_score(v.get('cadd_phred'))}\t{(v.get('interpretation') or '')[:36]}"
            )
        return 0 if hits else 1

    # local var19
    gene = args.gene.upper()
    path = resolve_data(root=args.root or project_root(), data=args.data)
    hits = []
    for v in iter_variants(path):
        if gene not in {g.upper() for g in v.genes}:
            continue
        if args.consequence and (
            not v.major_consequence
            or args.consequence.lower() not in v.major_consequence.lower()
        ):
            continue
        if args.min_af is not None and (v.joint_af is None or v.joint_af < args.min_af):
            continue
        if args.max_af is not None and (v.joint_af is None or v.joint_af > args.max_af):
            continue
        hits.append(v)
    hits.sort(key=lambda v: -(v.joint_af if v.joint_af is not None else -1.0))
    print(f"# gene={args.gene} file={path.name} matched={len(hits)}")
    print("variant_id\trsids\tconsequence\tjoint_AF\tCADD")
    for v in hits[: args.top]:
        print(
            f"{v.variant_id}\t{','.join(v.rsids) or 'NA'}\t"
            f"{v.major_consequence or 'NA'}\t{fmt_af(v.joint_af)}\t"
            f"{fmt_score(v.cadd_phred)}"
        )
    return 0 if hits else 1


if __name__ == "__main__":
    sys.exit(main())
