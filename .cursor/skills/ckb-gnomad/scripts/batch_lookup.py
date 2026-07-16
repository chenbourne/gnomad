#!/usr/bin/env python3
"""Batch rsID lookup via gnomAD API (max 20)."""
from __future__ import annotations

import argparse
import sys

from api_client import add_api_args, api_base, batch, fmt_af, use_api


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    add_api_args(p)
    p.add_argument("rsids", nargs="+", help="rsIDs (max 20)")
    args = p.parse_args()
    if args.local:
        print("batch requires API (no --local)", file=sys.stderr)
        return 2
    if not use_api(args):
        return 2
    base = api_base(args.api)
    try:
        data = batch(args.rsids[:20], base=base)
    except RuntimeError as exc:
        print(f"# API error ({base}): {exc}", file=sys.stderr)
        return 1
    print(f"# batch n={data.get('n')}  api={base}")
    print("rsid\tfound\tvariant_id\tjoint_AF\tinterpretation")
    for row in data.get("records") or []:
        v = row.get("variant") or {}
        print(
            f"{row.get('rsid')}\t{row.get('found')}\t"
            f"{v.get('variant_id') or '—'}\t{fmt_af(v.get('joint_af'))}\t"
            f"{(row.get('interpretation') or '')[:40]}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
