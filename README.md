# gnomAD local API

DuckDB + FastAPI over Spark/Hail-exported browser Parquet.

## Data (server)

Default root:

```text
/data/agent/gnomad/data/chrom=Y/*.parquet
```

Override:

```bash
export GNOMAD_PARQUET_ROOT=/data/agent/gnomad/data
```

## Run API

Always use a virtualenv before installing dependencies:

```bash
git clone https://github.com/chenbourne/gnomad.git
cd gnomad

# 1) create & activate venv (Python >= 3.9 recommended)
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2) install deps into the venv
pip install -U pip
pip install -r api/requirements.txt

# 3) start API
uvicorn api.app:app --host 0.0.0.0 --port 8088
```

Or one-shot helper:

```bash
bash api/start.sh
```

Later sessions:

```bash
cd gnomad
source .venv/bin/activate
uvicorn api.app:app --host 0.0.0.0 --port 8088
```

## Endpoints

```bash
curl http://127.0.0.1:8088/health
curl http://127.0.0.1:8088/chroms
curl 'http://127.0.0.1:8088/variant?q=Y:2781489'
curl 'http://127.0.0.1:8088/locus?chrom=Y&pos=2781489&window_kb=10'
```

Docs: `http://127.0.0.1:8088/docs`

## Cursor skill (API client)

Default API base: `http://10.221.12.63:8923` (override with `GNOMAD_API_BASE` / `--api`).

```bash
python .cursor/skills/ckb-gnomad/scripts/summary.py
python .cursor/skills/ckb-gnomad/scripts/lookup_variant.py 'Y:2781489'
python .cursor/skills/ckb-gnomad/scripts/locus_query.py --chr Y --pos 2781489 --window-kb 10
# local demo sample:
python .cursor/skills/ckb-gnomad/scripts/lookup_variant.py rs429358 --local
```

See `.cursor/skills/ckb-gnomad/SKILL.md`.
