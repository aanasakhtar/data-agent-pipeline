# Synthetic Customer Source

This is the fake "customer's database" that Airbyte pulls from. It exists so the
pipeline has a real, network-reachable Postgres source to sync from, instead of
Claude just reading a CSV directly — the whole point is hands-on practice with a
real ingestion connector.

## Usage

```
cd generator
pip install -r requirements.txt

# 1. Generate data as CSVs (no database needed yet — inspect before loading)
python generate_data.py

# 2. Load into a real Postgres (Neon) once you have a connection string
export DATABASE_URL=postgresql://user:pass@host/db?sslmode=require
python load_to_postgres.py
```

Re-running `generate_data.py` overwrites the CSVs in `output/` with a fresh random
dataset (same shape/scale, different rows) — useful for the `new-customer-onboarding`
skill's incremental-batch mode later.

See `../schema.sql` for the table definitions and `docs/decisions.md` (repo root) for
the chosen data scale.
