---
name: ckb-gnomad
description: >-
  gnomAD variant frequency toolkit for this repo (sample: var19.txt). Use for
  rsID/variant lookup, gene variant lists, locus windows, ancestry AF, CADD/REVEL,
  joint AF/grpmax/FAF, local gnomAD-style browser page (serve_viewer), or gnomAD
  questions on chr19 sample data. Scripts under .cursor/skills/ckb-gnomad/scripts/.
  Do not load nested JSON TSV ad-hoc in pandas.
---

# gnomAD variant toolkit (`var19.txt`)

**Scripts:** `.cursor/skills/ckb-gnomad/scripts/`  
**Run from project root:** this repo (`.../ckb/gnomad`).

## Data

| File | Notes |
|------|--------|
| **`var19.txt`** (default) | chr19 sample export: TSV + nested JSON (`joint` / VEP / predictors) |

Full-genome release not wired yet — same scripts will take `--data` later.

## Intent → script (read this first)

| 用户说法 | 必须用的脚本 |
|----------|----------------|
| **概况 / 有多少变异 / summary** | **`summary.py`** |
| **rs429358 / 这个 SNP 频率 / lookup** | **`lookup_variant.py`** |
| APOE 有哪些变异 / missense | `gene_variants.py -g APOE` |
| chr19:pos ± kb / 区域 | `locus_query.py --chr 19 --pos P` |
| EAS/AFR 等人群 AF | `af_by_ancestry.py --rsid …` |
| **官网风格变体页 / 浏览器页面** | **`serve_viewer.py`** |

## Default commands

```bash
# 概况
python .cursor/skills/ckb-gnomad/scripts/summary.py

# 按 rsID / variant_id / chrom:pos 查询（加 -v 看转录本）
python .cursor/skills/ckb-gnomad/scripts/lookup_variant.py rs429358
python .cursor/skills/ckb-gnomad/scripts/lookup_variant.py 19-44908684-T-C -v
python .cursor/skills/ckb-gnomad/scripts/lookup_variant.py 19:44908684

# 按基因
python .cursor/skills/ckb-gnomad/scripts/gene_variants.py -g APOE
python .cursor/skills/ckb-gnomad/scripts/gene_variants.py -g APOE --consequence missense

# 窗口（默认 ±50 kb）
python .cursor/skills/ckb-gnomad/scripts/locus_query.py --chr 19 --pos 44908684 --window-kb 50

# 人群频率
python .cursor/skills/ckb-gnomad/scripts/af_by_ancestry.py --rsid rs429358

# 本地变体浏览器（对齐 gnomAD 官网 Exomes/Genomes/Total + 人群表）
python .cursor/skills/ckb-gnomad/scripts/serve_viewer.py
# → http://127.0.0.1:8765/?q=19-44908684-T-C

# Parquet API（在有数据的服务器上启动；当前示例仅 chrom=Y）
# 默认数据目录: /data/agent/gnomad/data  （可用 GNOMAD_PARQUET_ROOT 覆盖）
# python3 -m venv .venv && source .venv/bin/activate
# pip install -r api/requirements.txt
# uvicorn api.app:app --host 0.0.0.0 --port 8088
# # 或: bash api/start.sh
# curl http://127.0.0.1:8088/health
# curl 'http://127.0.0.1:8088/variant?q=Y:2781489'
# curl 'http://127.0.0.1:8088/locus?chrom=Y&pos=2781489&window_kb=10'
```

## Agent checklist

1. Match intent with the table — **do not invent one-off pandas/json parsing** if a script exists.
2. Default data: `var19.txt` at repo root. Override with `--data PATH` if needed.
3. Report key fields: variant_id, rsids, genes, consequence, joint AF, grpmax, predictors.
4. Sample is chr19-only and tiny — say so if a query misses (other chromosomes / absent variants).

## Dependencies

Python 3.10+ stdlib only (`json`, `argparse`).

## Out of scope (this skill)

ClinVar pathogenicity calls, VEP re-annotation, full gnomAD download/ETL (later), Hail pipelines.
