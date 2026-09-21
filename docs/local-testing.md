# Local, Zero-Cost Testing (no Neon/Snowflake/Airbyte required)

This is a second, free path through the same dbt project, for testing the
pipeline and the CLaiMB skills without signing up for anything.

| Real path (docs/neon-setup.md etc.) | Local path (this doc) |
| --- | --- |
| Neon Postgres (source) | Synthetic CSVs directly |
| Airbyte Cloud (ingestion) | `dbt seed` loading `seeds/raw_*.csv` |
| Snowflake (warehouse) | DuckDB — an embedded, file-based warehouse (`dbt/customer_platform/dev.duckdb`) |
| `dbt build --target dev/ci` | `dbt build --target local` |

Nothing about the transformation layer changes — `models/staging/`,
`models/intermediate/`, `snapshots/`, `models/marts/` are the same files
either way (the staging models just branch on `target.name == 'local'` to
read a seed instead of a Snowflake source — see `models/staging/stg_*.sql`).

## Run it

```
# 1. Generate synthetic data (writes CSVs to data-source/generator/output/)
python data-source/generator/generate_data.py --seed 42

# 2. Copy them into dbt seeds (already done once; re-run after regenerating data)
cp data-source/generator/output/customers.csv        dbt/customer_platform/seeds/raw_customers.csv
cp data-source/generator/output/products.csv         dbt/customer_platform/seeds/raw_products.csv
cp data-source/generator/output/orders.csv           dbt/customer_platform/seeds/raw_orders.csv
cp data-source/generator/output/order_items.csv      dbt/customer_platform/seeds/raw_order_items.csv
cp data-source/generator/output/support_tickets.csv  dbt/customer_platform/seeds/raw_support_tickets.csv

# 3. Install dbt (one-time; ~150MB, no account needed)
pip install dbt-core dbt-duckdb

# 4. Build everything locally -- creates dbt/customer_platform/dev.duckdb
cd dbt/customer_platform
dbt seed --target local
dbt build --target local
```

`dbt build --target local` runs seeds, snapshots, models, and all schema
tests (`not_null`, `unique`, `relationships`, `accepted_values`) against
DuckDB. A clean run proves the entire bronze -> silver -> gold -> platinum
transformation logic is correct, independent of whether Snowflake/Airbyte
are ever set up.

## Querying the result

```
python -c "import duckdb; print(duckdb.connect('dev.duckdb').sql('select * from platinum.customer_360 limit 5'))"
```

(DuckDB's Python API works without any server — the whole warehouse is one
file, `dev.duckdb`, safe to delete and rebuild any time.)

## Using this for the CLaiMB skills pilot

The 11 skills under `.claude/skills/` (bronze-ingest-staging through
executive-synthesis) are written to work against exactly this local DuckDB
file — see `docs/claimb-idea-fit.md` for what they are and
`docs/claimb-pilot-run.md` for a worked example finding produced by running
them in sequence.
