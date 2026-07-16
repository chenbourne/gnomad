#!/usr/bin/env python3
"""List gnomAD variants overlapping a gene symbol (local var19.txt only; API has no /gene yet)."""
from __future__ import annotations

import argparse
import sys

from gnomad_io import add_data_args, fmt_af, fmt_score, iter_variants, project_root, resolve_data


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    add_data_args(p)
    p.add_argument("-g", "--gene", required=True, help="Gene symbol (e.g. APOE)")
    p.add_argument(
        "--consequence",
        default=None,
        help="Substring filter on major_consequence (e.g. missense)",
    )
    p.add_argument("--min-af", type=float, default=None, help="Min joint AF")
    p.add_argument("--max-af", type=float, default=None, help="Max joint AF")
    p.add_argument("--top", type=int, default=50, help="Max rows to print")
    args = p.parse_args()

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
    print(
        f"# gene={args.gene}  consequence={args.consequence or 'any'}  "
        f"matched={len(hits)}  file={path.name}"
    )
    print(
        "variant_id\trsids\tconsequence\tjoint_AF\tgrpmax_AF\tgrpmax_anc\t"
        "CADD\tHGVSc\tHGVSp"
    )
    for v in hits[: args.top]:
        print(
            f"{v.variant_id}\t{','.join(v.rsids) or 'NA'}\t"
            f"{v.major_consequence or 'NA'}\t{fmt_af(v.joint_af)}\t"
            f"{fmt_af(v.grpmax_af)}\t{v.grpmax_anc or 'NA'}\t"
            f"{fmt_score(v.cadd_phred)}\t"
            f"{v.hgvsc or ''}\t{v.hgvsp or ''}"
        )
    if len(hits) > args.top:
        print(f"# ... truncated; {len(hits) - args.top} more (raise --top)")
    return 0 if hits else 1


if __name__ == "__main__":
    sys.exit(main())
