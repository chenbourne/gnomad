#!/usr/bin/env python3
"""Summarize gnomAD API health / chrom coverage (or local var19.txt with --local)."""
from __future__ import annotations

import argparse
import sys
from collections import Counter

from api_client import add_api_args, api_base, chroms as api_chroms, health, use_api
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
    add_api_args(p)
    add_data_args(p)
    args = p.parse_args()

    if use_api(args):
        base = api_base(args.api)
        try:
            h = health(base)
            c = api_chroms(base)
        except RuntimeError as exc:
            print(f"# API error ({base}): {exc}", file=sys.stderr)
            return 1
        print(f"api:           {base}")
        print(f"ok:            {h.get('ok')}")
        print(f"dataset:       {h.get('dataset')}")
        print(f"parquet_root:  {h.get('parquet_root')}")
        print(f"chroms:        {', '.join(c.get('chroms') or h.get('chroms') or [])}")
        counts = h.get("variant_counts") or {}
        for chrom in h.get("chroms") or []:
            n = counts.get(chrom)
            if n is not None:
                print(f"chr{chrom}_variants: {n:,}")
        if h.get("total_variants") is not None:
            print(f"total:         {h['total_variants']:,}")
        elif h.get("chrY_variants") is not None:
            print(f"chrY_variants: {h.get('chrY_variants'):,}")
        if h.get("constraint_present") is not None:
            print(f"constraint:    {h.get('constraint_tsv')} ({'ok' if h.get('constraint_present') else 'missing'})")
        if h.get("error"):
            print(f"error:         {h['error']}")
        print("# partitions under GNOMAD_PARQUET_ROOT (e.g. chrom=9, chrom=Y)")
        return 0 if h.get("ok") else 1

    path = resolve_data(root=args.root or project_root(), data=args.data)
    n = 0
    by_chr: Counter[str] = Counter()
    afs: list[float] = []
    for v in iter_variants(path):
        n += 1
        by_chr[v.chrom] += 1
        if v.joint_af is not None:
            afs.append(v.joint_af)
    print(f"file:     {path}")
    print(f"variants: {n:,}")
    if afs:
        print(f"joint AF: min={fmt_af(min(afs))}  max={fmt_af(max(afs))}")
    for chrom, cnt in sorted(by_chr.items(), key=lambda x: chrom_sort_key(x[0])):
        print(f"  chr{chrom}: {cnt:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
