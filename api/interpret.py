"""ACMG-oriented AF interpretation (aligned with skills-v2 gnomad wording)."""
from __future__ import annotations

from typing import Any, Optional


def interpret_af(af: Optional[float]) -> str:
    if af is None:
        return "absent / 无数据 — 支持 PM2（人群罕见）方向，需结合覆盖度"
    if af == 0:
        return "absent (AC=0) — 人群中未见，支持 PM2"
    if af >= 0.05:
        return "常见 (AF≥5%) — 支持 BA1 良性证据，致病可能性低"
    if af >= 0.01:
        return "较常见 (AF≥1%) — 致病可能性较低，需结合 ClinVar"
    if af >= 0.001:
        return "低频 (0.1%≤AF<1%) — 需结合功能与 ClinVar 判断"
    return "极罕见 (AF<0.1%) — 与致病变异相容，需结合 ClinVar"


def best_af(variant: dict[str, Any]) -> Optional[float]:
    for key in ("joint_af", "exome_af", "genome_af"):
        af = variant.get(key)
        if af is not None:
            return float(af)
    return None


LOF_CONSEQUENCES = frozenset(
    {
        "stop_gained",
        "frameshift_variant",
        "splice_acceptor_variant",
        "splice_donor_variant",
        "start_lost",
        "transcript_ablation",
        "exon_loss_variant",
    }
)
