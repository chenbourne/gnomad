#!/usr/bin/env python3
"""Query gnomAD variants in a genomic window."""
from __future__ import annotations

import argparse
import sys

from gnomad_io import add_data_args, fmt_af, fmt_score, iter_variants, project_root, resolve_data


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    add_data_args(p)
    p.add_argument("--chr", required=True, help="Chromosome (e.g. 19 or chr19)")
    p.add_argument("--pos", type=int, required=True, help="Center position (bp)")
    p.add_argument("--window-kb", type=float, default=50.0, help="Half-window in kb")
    p.add_argument("--min-af", type=float, default=None)
    p.add_argument("--top", type=int, default=50)
    args = p.parse_args()

    chrom = str(args.chr).upper().removeprefix("CHR")
    half = int(args.window_kb * 1000)
    start = max(0, args.pos - half)
    end = args.pos + half

    path = resolve_data(root=args.root or project_root(), data=args.data)
    hits = []
    for v in iter_variants(path):
        if v.chrom != chrom:
            continue
        if v.pos < start or v.pos > end:
            continue
        if args.min_af is not None and (v.joint_af is None or v.joint_af < args.min_af):
            continue
        hits.append(v)

    hits.sort(key=lambda v: (v.pos, v.variant_id))
    print(
        f"# locus chr{chrom}:{start}-{end} (±{args.window_kb:g} kb around {args.pos}) "
        f"matched={len(hits)}  file={path.name}"
    )
    print("pos\tvariant_id\trsids\tgenes\tconsequence\tjoint_AF\tCADD")
    for v in hits[: args.top]:
        print(
            f"{v.pos}\t{v.variant_id}\t{','.join(v.rsids) or 'NA'}\t"
            f"{','.join(v.genes) or 'NA'}\t{v.major_consequence or 'NA'}\t"
            f"{fmt_af(v.joint_af)}\t"
            f"{fmt_score(v.cadd_phred)}"
        )
    if len(hits) > args.top:
        print(f"# ... truncated; {len(hits) - args.top} more (raise --top)")
    return 0 if hits else 1


if __name__ == "__main__":
    sys.exit(main())
