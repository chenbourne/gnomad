#!/usr/bin/env python3
"""Query gnomAD variants in a genomic window via API (default) or local file."""
from __future__ import annotations

import argparse
import sys

from api_client import add_api_args, api_base, fmt_af, fmt_score, locus as api_locus, use_api
from gnomad_io import add_data_args, iter_variants, project_root, resolve_data


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    add_api_args(p)
    add_data_args(p)
    p.add_argument("--chr", required=True, help="Chromosome (e.g. Y or 19)")
    p.add_argument("--pos", type=int, required=True, help="Center position (bp)")
    p.add_argument("--window-kb", type=float, default=50.0, help="Half-window in kb")
    p.add_argument("--top", type=int, default=50)
    args = p.parse_args()

    if use_api(args):
        base = api_base(args.api)
        try:
            data = api_locus(
                args.chr, args.pos, window_kb=args.window_kb, limit=args.top, base=base
            )
        except RuntimeError as exc:
            print(f"# API error ({base}): {exc}", file=sys.stderr)
            return 1
        hits = data.get("variants") or []
        print(
            f"# locus chr{args.chr} ±{args.window_kb:g} kb around {args.pos} "
            f"api={base} matched={len(hits)}"
        )
        print("pos\tvariant_id\trsids\tjoint_AF\texome_AF\tgenome_AF\tCADD")
        for v in hits:
            rs = ",".join(v.get("rsids") or []) or "NA"
            print(
                f"{v.get('pos')}\t{v.get('variant_id')}\t{rs}\t"
                f"{fmt_af(v.get('joint_af'))}\t{fmt_af(v.get('exome_af'))}\t"
                f"{fmt_af(v.get('genome_af'))}\t{fmt_score(v.get('cadd_phred'))}"
            )
        return 0 if hits else 1

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
        hits.append(v)
    hits.sort(key=lambda v: (v.pos, v.variant_id))
    print(
        f"# locus chr{chrom}:{start}-{end} (±{args.window_kb:g} kb) "
        f"file={path.name} matched={len(hits)}"
    )
    print("pos\tvariant_id\trsids\tgenes\tconsequence\tjoint_AF\tCADD")
    for v in hits[: args.top]:
        print(
            f"{v.pos}\t{v.variant_id}\t{','.join(v.rsids) or 'NA'}\t"
            f"{','.join(v.genes) or 'NA'}\t{v.major_consequence or 'NA'}\t"
            f"{fmt_af(v.joint_af)}\t{fmt_score(v.cadd_phred)}"
        )
    return 0 if hits else 1


if __name__ == "__main__":
    sys.exit(main())
