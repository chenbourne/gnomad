#!/usr/bin/env python3
"""Summarize gnomAD sample TSV (variant counts, AF, consequences, genes)."""
from __future__ import annotations

import argparse
import sys
from collections import Counter

from gnomad_io import (
    add_data_args,
    chrom_sort_key,
    fmt_af,
    iter_variants,
    project_root,
    resolve_data,
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    add_data_args(p)
    args = p.parse_args()

    path = resolve_data(root=args.root or project_root(), data=args.data)
    n = 0
    n_exome = n_genome = n_rsid = 0
    afs: list[float] = []
    by_chr: Counter[str] = Counter()
    by_cons: Counter[str] = Counter()
    genes: Counter[str] = Counter()
    max_af_v = None

    for v in iter_variants(path):
        n += 1
        by_chr[v.chrom] += 1
        if v.has_exome:
            n_exome += 1
        if v.has_genome:
            n_genome += 1
        if v.rsids:
            n_rsid += 1
        if v.joint_af is not None:
            afs.append(v.joint_af)
            if max_af_v is None or v.joint_af > (max_af_v.joint_af or 0):
                max_af_v = v
        if v.major_consequence:
            by_cons[v.major_consequence] += 1
        for g in v.genes:
            genes[g] += 1

    print(f"file:     {path}")
    print(f"size:     {path.stat().st_size / 1024:.1f} KB")
    print(f"variants: {n:,}")
    print(f"with rsid: {n_rsid:,}")
    print(f"exome call: {n_exome:,}  genome call: {n_genome:,}")
    if afs:
        print(
            f"joint AF:  min={fmt_af(min(afs))}  max={fmt_af(max(afs))}  "
            f"median={fmt_af(sorted(afs)[len(afs) // 2])}"
        )
    if max_af_v:
        print(
            f"highest AF: {max_af_v.variant_id}  AF={fmt_af(max_af_v.joint_af)}  "
            f"genes={','.join(max_af_v.genes) or 'NA'}  "
            f"cons={max_af_v.major_consequence or 'NA'}"
        )
    print("--- variants per chromosome ---")
    for chrom, cnt in sorted(by_chr.items(), key=lambda x: chrom_sort_key(x[0])):
        print(f"  chr{chrom}: {cnt:,}")
    if by_cons:
        print("--- major consequence ---")
        for cons, cnt in by_cons.most_common():
            print(f"  {cons}: {cnt}")
    if genes:
        print("--- genes (variant count) ---")
        for g, cnt in genes.most_common():
            print(f"  {g}: {cnt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
