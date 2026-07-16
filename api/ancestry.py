"""Ancestry group labels and table ordering (gnomAD browser style)."""
from __future__ import annotations

from typing import Any, Optional

ANC_LABELS = {
    "afr": "African/African American",
    "ami": "Amish",
    "amr": "Admixed American",
    "asj": "Ashkenazi Jewish",
    "eas": "East Asian",
    "fin": "European (Finnish)",
    "mid": "Middle Eastern",
    "nfe": "European (non-Finnish)",
    "sas": "South Asian",
    "remaining": "Remaining",
    "XX": "XX",
    "XY": "XY",
}

ANC_ORDER = (
    "afr",
    "fin",
    "nfe",
    "remaining",
    "ami",
    "asj",
    "amr",
    "sas",
    "eas",
    "mid",
)


def af(ac: Any, an: Any) -> Optional[float]:
    if ac is None or an is None or an == 0:
        return None
    return float(ac) / float(an)


def parse_ancestry_groups(raw: Any) -> list[dict[str, Any]]:
    """Normalize DuckDB/JSON ancestry_groups list to browser-like rows."""
    if raw is None:
        return []
    if isinstance(raw, str):
        import json

        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []

    by_id: dict[str, dict] = {}
    for item in raw:
        g = _as_dict(item)
        if not g:
            continue
        gid = g.get("id")
        if not gid or gid.endswith("_XX") or gid.endswith("_XY"):
            continue
        if gid not in by_id:
            by_id[gid] = g

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for gid in list(ANC_ORDER) + ["XX", "XY"]:
        g = by_id.get(gid)
        if not g:
            continue
        rows.append(_row(gid, g))
        seen.add(gid)
    for gid in sorted(by_id):
        if gid in seen:
            continue
        rows.append(_row(gid, by_id[gid]))
    return rows


def _as_dict(item: Any) -> dict | None:
    if item is None:
        return None
    if isinstance(item, dict):
        return item
    # duckdb struct / named tuple
    if hasattr(item, "_asdict"):
        return item._asdict()
    if hasattr(item, "keys"):
        return dict(item)
    return None


def _row(gid: str, g: dict) -> dict[str, Any]:
    ac, an = g.get("ac"), g.get("an")
    return {
        "id": gid,
        "label": ANC_LABELS.get(gid, gid),
        "ac": ac,
        "an": an,
        "homozygote_count": g.get("homozygote_count"),
        "af": af(ac, an),
    }
