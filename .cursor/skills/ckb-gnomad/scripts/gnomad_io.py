"""Shared paths and parser for gnomAD variant TSV (nested JSON columns)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterator, NamedTuple

DEFAULT_DATA = "var19.txt"

# Continental / cohort ancestry ids (exclude sex-split XX/XY and empty).
MAIN_ANC = ("afr", "amr", "asj", "eas", "fin", "mid", "nfe", "sas", "ami", "remaining")


class Variant(NamedTuple):
    chrom: str
    pos: int
    ref: str
    alt: str
    variant_id: str
    rsids: tuple[str, ...]
    caid: str | None
    genes: tuple[str, ...]
    major_consequence: str | None
    hgvsc: str | None
    hgvsp: str | None
    joint_ac: int | None
    joint_an: int | None
    joint_af: float | None
    joint_hom: int | None
    grpmax_af: float | None
    grpmax_anc: str | None
    faf95_max: float | None
    faf95_max_anc: str | None
    cadd_phred: float | None
    revel_max: float | None
    spliceai_ds_max: float | None
    filters_exome: tuple[str, ...]
    filters_genome: tuple[str, ...]
    flags_joint: tuple[str, ...]
    ancestry_af: dict[str, float]  # id -> AF (ac/an) for MAIN_ANC + raw ids present
    has_exome: bool
    has_genome: bool
    raw: dict[str, Any]  # original parsed columns for deep dives


def project_root() -> Path:
    """Repo root = .../ckb/gnomad (scripts → skill → skills → .cursor → root)."""
    return Path(__file__).resolve().parents[4]


def resolve_data(root: Path | None = None, data: Path | None = None) -> Path:
    if data is not None:
        path = data if data.is_absolute() else (root or project_root()) / data
    else:
        path = (root or project_root()) / DEFAULT_DATA
    if not path.is_file():
        raise FileNotFoundError(f"Missing gnomAD data file: {path}")
    return path


def add_data_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Project root containing data files (default: auto)",
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=None,
        help=f"Data TSV path (default: {DEFAULT_DATA} under root)",
    )


def _loads(val: str) -> Any:
    if val in ("", "NA", "null", "None"):
        return None
    try:
        return json.loads(val)
    except json.JSONDecodeError:
        return val


def _parse_locus(locus: str) -> tuple[str, int]:
    # chr19:1839149
    chrom, pos_s = locus.rsplit(":", 1)
    chrom = chrom.removeprefix("chr").removeprefix("CHR")
    return chrom, int(pos_s)


def _af(block: dict | None) -> tuple[int | None, int | None, float | None, int | None]:
    if not isinstance(block, dict):
        return None, None, None, None
    ac = block.get("ac")
    an = block.get("an")
    hom = block.get("homozygote_count")
    if ac is None or an is None or an == 0:
        return ac, an, None, hom
    return int(ac), int(an), float(ac) / float(an), int(hom) if hom is not None else None


def _ancestry_afs(freq_all: dict | None) -> dict[str, float]:
    out: dict[str, float] = {}
    if not isinstance(freq_all, dict):
        return out
    groups = freq_all.get("ancestry_groups") or []
    for g in groups:
        if not isinstance(g, dict):
            continue
        gid = g.get("id")
        if not gid or gid in ("XX", "XY", ""):
            continue
        if gid.endswith("_XX") or gid.endswith("_XY"):
            continue
        ac, an = g.get("ac"), g.get("an")
        if ac is None or an is None or an == 0:
            continue
        out[str(gid)] = float(ac) / float(an)
    return out


def _genes_and_consequence(tc: list | None) -> tuple[tuple[str, ...], str | None, str | None, str | None]:
    if not isinstance(tc, list) or not tc:
        return (), None, None, None
    genes = tuple(sorted({t.get("gene_symbol") for t in tc if isinstance(t, dict) and t.get("gene_symbol")}))
    canon = [t for t in tc if isinstance(t, dict) and t.get("is_canonical")]
    pick = canon[0] if canon else (tc[0] if isinstance(tc[0], dict) else None)
    if not pick:
        return genes, None, None, None
    return (
        genes,
        pick.get("major_consequence") or (pick.get("consequence_terms") or [None])[0],
        pick.get("hgvsc"),
        pick.get("hgvsp"),
    )


def row_to_variant(cols: dict[str, str]) -> Variant | None:
    locus = cols.get("locus") or ""
    if not locus or ":" not in locus:
        return None
    chrom, pos = _parse_locus(locus)
    alleles = _loads(cols.get("alleles", "NA"))
    if not isinstance(alleles, list) or len(alleles) < 2:
        ref, alt = ".", "."
    else:
        ref, alt = str(alleles[0]), str(alleles[1])

    variant_id = cols.get("variant_id") or f"{chrom}-{pos}-{ref}-{alt}"
    rsids_raw = _loads(cols.get("rsids", "NA"))
    rsids: tuple[str, ...] = ()
    if isinstance(rsids_raw, list):
        rsids = tuple(str(x) for x in rsids_raw if x)
    elif isinstance(rsids_raw, str) and rsids_raw:
        rsids = (rsids_raw,)

    caid = cols.get("caid")
    if caid in ("", "NA", "null", None):
        caid = None

    joint = _loads(cols.get("joint", "NA"))
    exome = _loads(cols.get("exome", "NA"))
    genome = _loads(cols.get("genome", "NA"))
    predictors = _loads(cols.get("in_silico_predictors", "NA"))
    tc = _loads(cols.get("transcript_consequences", "NA"))

    # Prefer top-level transcript_consequences; else VEP from genome/exome.
    if not isinstance(tc, list):
        for block in (genome, exome):
            if isinstance(block, dict):
                vep = block.get("vep115") or {}
                if isinstance(vep, dict) and vep.get("transcript_consequences"):
                    tc = vep["transcript_consequences"]
                    break

    genes, maj, hgvsc, hgvsp = _genes_and_consequence(tc if isinstance(tc, list) else None)

    joint_ac = joint_an = joint_hom = None
    joint_af = grpmax_af = faf95_max = None
    grpmax_anc = faf95_max_anc = None
    flags_joint: tuple[str, ...] = ()
    ancestry_af: dict[str, float] = {}

    if isinstance(joint, dict):
        freq = joint.get("freq") or {}
        freq_all = freq.get("all") if isinstance(freq, dict) else None
        joint_ac, joint_an, joint_af, joint_hom = _af(freq_all if isinstance(freq_all, dict) else None)
        ancestry_af = _ancestry_afs(freq_all if isinstance(freq_all, dict) else None)
        grp = joint.get("grpmax")
        if isinstance(grp, dict):
            grpmax_af = grp.get("AF")
            grpmax_anc = grp.get("gen_anc")
        faf = joint.get("fafmax")
        if isinstance(faf, dict):
            faf95_max = faf.get("faf95_max")
            faf95_max_anc = faf.get("faf95_max_gen_anc")
        flags = joint.get("flags") or []
        if isinstance(flags, list):
            flags_joint = tuple(str(x) for x in flags)

    filters_exome: tuple[str, ...] = ()
    filters_genome: tuple[str, ...] = ()
    if isinstance(exome, dict):
        fe = exome.get("filters") or []
        if isinstance(fe, list):
            filters_exome = tuple(str(x) for x in fe)
    if isinstance(genome, dict):
        fg = genome.get("filters") or []
        if isinstance(fg, list):
            filters_genome = tuple(str(x) for x in fg)

    cadd_phred = revel_max = spliceai = None
    if isinstance(predictors, dict):
        cadd = predictors.get("cadd") or {}
        if isinstance(cadd, dict):
            cadd_phred = cadd.get("phred")
        revel_max = predictors.get("revel_max")
        spliceai = predictors.get("spliceai_ds_max")

    raw = {k: _loads(v) if k not in ("locus", "variant_id", "caid") else v for k, v in cols.items()}

    return Variant(
        chrom=chrom,
        pos=pos,
        ref=ref,
        alt=alt,
        variant_id=variant_id,
        rsids=rsids,
        caid=caid,
        genes=genes,
        major_consequence=maj,
        hgvsc=hgvsc,
        hgvsp=hgvsp,
        joint_ac=joint_ac,
        joint_an=joint_an,
        joint_af=joint_af,
        joint_hom=joint_hom,
        grpmax_af=grpmax_af,
        grpmax_anc=grpmax_anc,
        faf95_max=faf95_max,
        faf95_max_anc=faf95_max_anc,
        cadd_phred=cadd_phred,
        revel_max=revel_max,
        spliceai_ds_max=spliceai,
        filters_exome=filters_exome,
        filters_genome=filters_genome,
        flags_joint=flags_joint,
        ancestry_af=ancestry_af,
        has_exome=isinstance(exome, dict),
        has_genome=isinstance(genome, dict),
        raw=raw,
    )


def iter_variants(path: Path) -> Iterator[Variant]:
    with path.open("r", buffering=1024 * 1024) as fh:
        header = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            cols = {header[i]: parts[i] if i < len(parts) else "" for i in range(len(header))}
            v = row_to_variant(cols)
            if v is not None:
                yield v


def load_variants(path: Path) -> list[Variant]:
    return list(iter_variants(path))


def chrom_sort_key(chrom: str) -> tuple[int, str]:
    c = chrom.upper().removeprefix("CHR")
    if c.isdigit():
        return (int(c), "")
    if c == "X":
        return (23, "")
    if c == "Y":
        return (24, "")
    if c in ("MT", "M"):
        return (25, "")
    return (99, c)


def fmt_af(af: float | None) -> str:
    if af is None:
        return "NA"
    if af == 0:
        return "0"
    if af >= 0.01:
        return f"{af:.4g}"
    return f"{af:.3e}"


def fmt_score(x: float | None, digits: int = 3) -> str:
    if x is None:
        return "NA"
    return f"{x:.{digits}g}"


def match_rsid(v: Variant, rsid: str) -> bool:
    target = rsid.lower().removeprefix("rs")
    for r in v.rsids:
        if r.lower().removeprefix("rs") == target:
            return True
    return False


def match_variant_id(v: Variant, vid: str) -> bool:
    a = vid.upper().removeprefix("CHR")
    b = v.variant_id.upper().removeprefix("CHR")
    return a == b
