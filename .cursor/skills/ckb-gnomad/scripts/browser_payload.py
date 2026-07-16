"""Build gnomAD-browser-style JSON payloads from local TSV rows."""
from __future__ import annotations

from typing import Any

from gnomad_io import MAIN_ANC, Variant, match_rsid, match_variant_id

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

# Display order for ancestry table (browser-like); XX/XY appended last.
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


def _af(ac: int | None, an: int | None) -> float | None:
    if ac is None or an is None or an == 0:
        return None
    return float(ac) / float(an)


def _freq_all(block: dict | None) -> dict | None:
    if not isinstance(block, dict):
        return None
    freq = block.get("freq") or {}
    if not isinstance(freq, dict):
        return None
    all_b = freq.get("all")
    return all_b if isinstance(all_b, dict) else None


def _ancestry_rows(freq_all: dict | None) -> list[dict[str, Any]]:
    if not freq_all:
        return []
    by_id: dict[str, dict] = {}
    for g in freq_all.get("ancestry_groups") or []:
        if not isinstance(g, dict):
            continue
        gid = g.get("id")
        if not gid or gid.endswith("_XX") or gid.endswith("_XY"):
            continue
        # Prefer first occurrence (sex-split duplicates exist as bare XX/XY)
        if gid not in by_id:
            by_id[gid] = g

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for gid in list(ANC_ORDER) + ["XX", "XY"]:
        g = by_id.get(gid)
        if not g:
            continue
        ac, an = g.get("ac"), g.get("an")
        rows.append(
            {
                "id": gid,
                "label": ANC_LABELS.get(gid, gid),
                "ac": ac,
                "an": an,
                "homozygote_count": g.get("homozygote_count"),
                "af": _af(ac, an),
            }
        )
        seen.add(gid)
    # Any other main continental ids not in ANC_ORDER
    for gid in MAIN_ANC:
        if gid in seen:
            continue
        g = by_id.get(gid)
        if not g:
            continue
        ac, an = g.get("ac"), g.get("an")
        rows.append(
            {
                "id": gid,
                "label": ANC_LABELS.get(gid, gid),
                "ac": ac,
                "an": an,
                "homozygote_count": g.get("homozygote_count"),
                "af": _af(ac, an),
            }
        )
    return rows


def _faf95(block: dict | None, *, exome: bool = False) -> float | None:
    if not isinstance(block, dict):
        return None
    faf = block.get("fafmax")
    if not isinstance(faf, dict):
        return None
    if exome:
        # exome nests under gnomad / non_ukb
        g = faf.get("gnomad")
        if isinstance(g, dict) and g.get("faf95_max") is not None:
            return float(g["faf95_max"])
    if faf.get("faf95_max") is not None:
        return float(faf["faf95_max"])
    return None


def _summary_block(
    label: str,
    freq_all: dict | None,
    *,
    filters: list[str] | None = None,
    flags: list[str] | None = None,
    faf95: float | None = None,
    present: bool = True,
) -> dict[str, Any]:
    if not present or not freq_all:
        return {
            "label": label,
            "present": False,
            "filters": [],
            "filter_display": "—",
            "ac": None,
            "an": None,
            "af": None,
            "faf95": None,
            "homozygote_count": None,
        }
    ac, an = freq_all.get("ac"), freq_all.get("an")
    filt = list(filters or [])
    flag_list = list(flags or [])
    if flag_list:
        pretty = []
        for f in flag_list:
            if f == "discrepant_frequencies":
                pretty.append("Discrepant frequencies")
            else:
                pretty.append(f.replace("_", " ").capitalize())
        filter_display = ", ".join(pretty)
        filter_kind = "warning"
    elif filt:
        filter_display = ", ".join(filt)
        filter_kind = "fail"
    else:
        filter_display = "Pass"
        filter_kind = "pass"
    return {
        "label": label,
        "present": True,
        "filters": filt,
        "flags": flag_list,
        "filter_display": filter_display,
        "filter_kind": filter_kind,
        "ac": ac,
        "an": an,
        "af": _af(ac, an),
        "faf95": faf95,
        "homozygote_count": freq_all.get("homozygote_count"),
    }


def browser_payload(v: Variant) -> dict[str, Any]:
    """Shape one variant like the gnomAD browser variant page."""
    exome = v.raw.get("exome") if isinstance(v.raw.get("exome"), dict) else None
    genome = v.raw.get("genome") if isinstance(v.raw.get("genome"), dict) else None
    joint = v.raw.get("joint") if isinstance(v.raw.get("joint"), dict) else None

    ex_freq = _freq_all(exome)
    gn_freq = _freq_all(genome)
    jt_freq = None
    if isinstance(joint, dict):
        freq = joint.get("freq") or {}
        if isinstance(freq, dict) and isinstance(freq.get("all"), dict):
            jt_freq = freq["all"]

    ex_filters = list((exome or {}).get("filters") or []) if exome else []
    gn_filters = list((genome or {}).get("filters") or []) if genome else []
    jt_flags = list((joint or {}).get("flags") or []) if joint else []

    summary = {
        "exome": _summary_block(
            "Exomes",
            ex_freq,
            filters=ex_filters,
            faf95=_faf95(exome, exome=True),
            present=exome is not None,
        ),
        "genome": _summary_block(
            "Genomes",
            gn_freq,
            filters=gn_filters,
            faf95=_faf95(genome),
            present=genome is not None,
        ),
        "joint": _summary_block(
            "Total",
            jt_freq,
            flags=jt_flags,
            faf95=_faf95(joint),
            present=joint is not None,
        ),
    }

    ancestry = {
        "exome": _ancestry_rows(ex_freq),
        "genome": _ancestry_rows(gn_freq),
        "joint": _ancestry_rows(jt_freq),
    }

    allele_type = "SNV" if len(v.ref) == 1 and len(v.alt) == 1 else "InDel"

    genes = list(v.genes)
    primary_gene = genes[0] if genes else None

    resources = {
        "dbsnp": [{"id": r, "url": f"https://www.ncbi.nlm.nih.gov/snp/{r}"} for r in v.rsids],
        "ucsc": (
            f"https://genome.ucsc.edu/cgi-bin/hgTracks?db=hg38"
            f"&position=chr{v.chrom}%3A{v.pos}-{v.pos}"
        ),
        "clingen": (
            {"id": v.caid, "url": f"https://reg.clinicalgenome.org/redmine/projects/registry/genboree_registry/by_caid?caid={v.caid}"}
            if v.caid
            else None
        ),
        "gnomad": f"https://gnomad.broadinstitute.org/variant/{v.variant_id}?dataset=gnomad_r4",
    }

    return {
        "variant_id": v.variant_id,
        "chrom": v.chrom,
        "pos": v.pos,
        "ref": v.ref,
        "alt": v.alt,
        "reference_genome": "GRCh38",
        "allele_type": allele_type,
        "dataset_label": "gnomAD v4 (local sample)",
        "rsids": list(v.rsids),
        "caid": v.caid,
        "genes": genes,
        "primary_gene": primary_gene,
        "consequence": v.major_consequence,
        "hgvsc": v.hgvsc,
        "hgvsp": v.hgvsp,
        "predictors": {
            "cadd_phred": v.cadd_phred,
            "revel_max": v.revel_max,
            "spliceai_ds_max": v.spliceai_ds_max,
        },
        "summary": summary,
        "ancestry": ancestry,
        "resources": resources,
    }


def find_variants(variants: list[Variant], query: str) -> list[Variant]:
    q = query.strip()
    if not q:
        return []
    low = q.lower()
    hits: list[Variant] = []
    for v in variants:
        if low.startswith("rs") and match_rsid(v, q):
            hits.append(v)
            continue
        if "-" in q and match_variant_id(v, q):
            hits.append(v)
            continue
        if ":" in q:
            parts = q.replace("chr", "").replace("CHR", "").split(":")
            try:
                chrom, pos = parts[0], int(parts[1])
            except (IndexError, ValueError):
                continue
            if v.chrom == chrom and v.pos == pos:
                if len(parts) >= 4 and (v.ref != parts[2] or v.alt != parts[3]):
                    continue
                hits.append(v)
            continue
        # bare gene-ish fallback: exact gene symbol
        if q.upper() in {g.upper() for g in v.genes}:
            hits.append(v)
    return hits


def index_list(variants: list[Variant]) -> list[dict[str, Any]]:
    rows = []
    for v in variants:
        rows.append(
            {
                "variant_id": v.variant_id,
                "rsids": list(v.rsids),
                "genes": list(v.genes),
                "consequence": v.major_consequence,
                "joint_af": v.joint_af,
                "chrom": v.chrom,
                "pos": v.pos,
            }
        )
    rows.sort(key=lambda r: (r["chrom"], r["pos"], r["variant_id"]))
    return rows
