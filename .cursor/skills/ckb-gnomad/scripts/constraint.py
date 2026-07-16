#!/usr/bin/env python3
"""Query gnomAD gene constraint (pLI/LOEUF) via API — needs constraint TSV on server."""
from __future__ import annotations

import argparse
import sys

from api_client import add_api_args, api_base, constraint, use_api


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    add_api_args(p)
    p.add_argument("gene", help="Gene symbol, e.g. BRCA1")
    args = p.parse_args()
    if args.local or not use_api(args):
        print("constraint requires API + constraint TSV on server", file=sys.stderr)
        return 2
    base = api_base(args.api)
    try:
        data = constraint(args.gene, base=base)
    except RuntimeError as exc:
        print(f"# API error ({base}): {exc}", file=sys.stderr)
        return 1
    c = data.get("constraint") or {}
    print(f"# gene={data.get('gene')}  api={base}")
    print(f"pLI:    {c.get('pLI')}")
    print(f"LOEUF:  {c.get('LOEUF')}")
    print(f"oe_lof: {c.get('oe_lof')}  oe_mis: {c.get('oe_mis')}")
    print(f"lof_z:  {c.get('lof_z')}  mis_z: {c.get('mis_z')}")
    print(f"interpret: {data.get('interpretation')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
