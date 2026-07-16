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

```bash
git clone https://github.com/chenbourne/gnomad.git
cd gnomad
pip install -r api/requirements.txt
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

## Cursor skill

See `.cursor/skills/ckb-gnomad/` for local `var19.txt` toolkit (demo). API is the shareable path for full Parquet on the server.
