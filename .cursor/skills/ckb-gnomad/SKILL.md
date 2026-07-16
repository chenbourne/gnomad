---
name: ckb-gnomad
description: >-
  gnomAD variant frequency toolkit. Default: call remote Parquet API
  (http://10.221.12.63:8923). Use for rsID/variant lookup, locus windows, AF,
  API health/chroms, or --local var19.txt demo. Scripts under
  .cursor/skills/ckb-gnomad/scripts/. Do not scrape gnomAD GraphQL, do not invent
  ad-hoc pandas over TSV.
---

# gnomAD variant toolkit (API-first)

**Scripts:** `.cursor/skills/ckb-gnomad/scripts/`  
**Run from project root:** this repo (`.../ckb/gnomad`).

## Data backend

| Mode | How | Notes |
|------|-----|--------|
| **API (default)** | `http://10.221.12.63:8923` | Parquet on server (`/data/agent/gnomad/data`); currently **chrY** |
| Local demo | `--local` → `var19.txt` | chr19 sample only |

Override API: `export GNOMAD_API_BASE=http://host:port` or `--api URL`.

## Intent → script

| 用户说法 | 脚本 |
|----------|------|
| **概况 / 有哪些染色体 / API 是否通** | **`summary.py`** |
| **查位点 / rsID / 频率** | **`lookup_variant.py`** |
| 区域 ± kb | `locus_query.py --chr Y --pos P` |
| 人群 AF 大表 | `lookup_variant.py`（API 返回 `ancestry` + `summary`） |
| 本地样例（无 API） | 同上脚本加 **`--local`** |
| 官网风格页（本地样例） | `serve_viewer.py`（读 var19.txt） |

## Default commands (API)

```bash
# 概况（染色体分区、chrY 条数）
python .cursor/skills/ckb-gnomad/scripts/summary.py

# 查位点（当前服务有 chrom=Y）
python .cursor/skills/ckb-gnomad/scripts/lookup_variant.py 'Y:2781489'
python .cursor/skills/ckb-gnomad/scripts/lookup_variant.py Y-2781489-C-T

# 窗口
python .cursor/skills/ckb-gnomad/scripts/locus_query.py --chr Y --pos 2781489 --window-kb 10

# 指定 API
python .cursor/skills/ckb-gnomad/scripts/lookup_variant.py 'Y:2781489' --api http://10.221.12.63:8923

# 回退本地 var19.txt
python .cursor/skills/ckb-gnomad/scripts/lookup_variant.py rs429358 --local
```

## Agent checklist

1. **Default to API** — do not use `--local` unless user asks for the sample file or API is down.
2. Server currently has **chrY only** — queries like `1:2781489` / chr19 will fail until more `chrom=*` partitions exist; say so.
3. Prefer example `Y:2781489` / `Y-2781489-C-T` when demonstrating.
4. Report **summary** (Exomes/Genomes/Total) and **ancestry** tables from API JSON when present.
5. Do not call gnomAD public GraphQL for this skill.

## Dependencies

- API mode: Python 3.10+ **stdlib only** (`urllib`)
- Local mode: stdlib (`json`)
- Server API stack: see repo `api/` (venv + `api/requirements.txt`)

## Out of scope

ClinVar calls, VEP re-annotation, Hail ETL, gene-constraint endpoints (not in API yet).
