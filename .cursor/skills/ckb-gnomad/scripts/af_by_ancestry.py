#!/usr/bin/env python3
"""Print joint allele frequencies by ancestry for one variant."""
from __future__ import annotations

import argparse
import sys

from gnomad_io import (
    MAIN_ANC,
    add_data_args,
    fmt_af,
    iter_variants,
    match_rsid,
    match_variant_id,
    project_root,
    resolve_data,
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    add_data_args(p)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--rsid", help="rsID (e.g. rs429358)")
    g.add_argument("--variant-id", help="e.g. 19-44908684-T-C")
    p.add_argument(
        "--all-groups",
        action="store_true",
        help="Include every ancestry id present (not only MAIN_ANC)",
    )
    args = p.parse_args()

    path = resolve_data(root=args.root or project_root(), data=args.data)
    hits = []
    for v in iter_variants(path):
        if args.rsid and match_rsid(v, args.rsid):
            hits.append(v)
        elif args.variant_id and match_variant_id(v, args.variant_id):
            hits.append(v)

    if not hits:
        print("No match.")
        return 1

    for i, v in enumerate(hits):
        if i:
            print("---")
        print(f"# {v.variant_id}  rsids={','.join(v.rsids) or 'NA'}")
        print(f"# joint overall AF={fmt_af(v.joint_af)}  AC={v.joint_ac}  AN={v.joint_an}")
        print("ancestry\tAF")
        if args.all_groups:
            keys = sorted(v.ancestry_af.keys())
        else:
            keys = [a for a in MAIN_ANC if a in v.ancestry_af]
            # also any extra non-sex groups
            for k in sorted(v.ancestry_af):
                if k not in keys and not k.endswith("_XX") and not k.endswith("_XY"):
                    keys.append(k)
        for k in keys:
            print(f"{k}\t{fmt_af(v.ancestry_af[k])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
