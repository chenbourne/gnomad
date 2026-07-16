---
name: ckb-gnomad
description: >-
  gnomAD variant frequency toolkit. Default: call remote Parquet API
  (http://10.221.12.63:8923). Use for rsID/variant lookup, locus windows, AF,
  ancestry tables, ACMG-style rarity, batch rsID, gene rare/lof/missense filters,
  gene constraint (if TSV on server), API health, or --local var19.txt demo.
  Scripts under .cursor/skills/ckb-gnomad/scripts/. Do not scrape gnomAD GraphQL.
---

# gnomAD variant toolkit (API-first)

**Scripts:** `.cursor/skills/ckb-gnomad/scripts/`  
**Run from project root:** this repo (`.../ckb/gnomad`).

## Data backend

| Mode | How | Notes |
|------|-----|--------|
| **API (default)** | `http://10.221.12.63:8923` | Parquet on server; currently **chrY** (+ more as exported) |
| Local demo | `--local` → `var19.txt` | chr19 sample only |
| Gene constraint | `/constraint` | Uses `gnomad.v4.1.constraint_metrics.tsv.gz` in repo (or server path) |

Override API: `export GNOMAD_API_BASE=...` or `--api URL`.

## Intent → script

| 用户说法 | 脚本 |
|----------|------|
| **概况 / 染色体 / API** | **`summary.py`** |
| **查位点 / 频率 / 解读** | **`lookup_variant.py`** |
| 区域 ± kb | `locus_query.py --chr Y --pos P` |
| **批量 rsID** | **`batch_lookup.py rs1 rs2 …`** |
| **基因 rare/lof/missense** | **`gene_variants.py -g GENE --mode rare --chrom Y`** |
| **基因约束 pLI/LOEUF** | **`constraint.py GENE`**（需服务器约束 TSV） |
| Web | `http://10.221.12.63:8923/ui/` 或 `serve_web.py` |
| 本地样例 | 脚本加 **`--local`** |

## Default commands

```bash
python .cursor/skills/ckb-gnomad/scripts/summary.py
python .cursor/skills/ckb-gnomad/scripts/lookup_variant.py Y-2781489-C-T
python .cursor/skills/ckb-gnomad/scripts/locus_query.py --chr Y --pos 2781489 --window-kb 10
python .cursor/skills/ckb-gnomad/scripts/batch_lookup.py rs123 rs456
python .cursor/skills/ckb-gnomad/scripts/gene_variants.py -g SRY --mode rare --chrom Y
python .cursor/skills/ckb-gnomad/scripts/constraint.py BRCA1
python .cursor/skills/ckb-gnomad/scripts/lookup_variant.py rs429358 --local
```

## Agent checklist

1. Default to API; `--local` only for var19 demo or API down.
2. chrY-only until more `chrom=*` partitions exist.
3. Report summary + ancestry + **interpretation** when present.
4. Constraint needs server TSV — if 404, say how to install the file.
5. Do not call public gnomAD GraphQL from this skill.

## Still not in this skill (vs skills-v2)

- Multi-dataset switch (`gnomad_r2` / `r3`) — need separate Parquet exports  
- Full-genome until all chrom Parquet partitions are loaded  

## Dependencies

API mode: stdlib. Server: see `api/requirements.txt`.
