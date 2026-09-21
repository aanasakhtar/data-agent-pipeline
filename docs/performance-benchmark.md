# Performance Benchmark — Source to Medallion, at Scale

Answers the question "how will this perform, source to medallion" with a
real measurement instead of an estimate. Ran locally, zero cost, via
`data-source/generator/generate_data.py`'s new `--customers/--products/
--orders/--order-items/--support-tickets/--output-dir` overrides.

## Setup

Two runs compared:

| | Demo scale (committed) | Benchmark scale (100x) |
| --- | --- | --- |
| customers | 200 | 20,000 |
| products | 50 | 200 |
| orders | 2,000 | 200,000 |
| order_items | 5,000 | 500,000 |
| support_tickets | 500 | 50,000 |
| **total rows** | 7,755 | 770,205 |

Benchmark data was generated to a scratch directory, swapped into
`dbt/customer_platform/seeds/` temporarily, built into a separate
`bench.duckdb` (via `DUCKDB_PATH` env var, never touching the committed
`dev.duckdb`), measured, then the original demo seeds were restored and
`dev.duckdb` rebuilt back to its committed state. Nothing in git history
or the committed dataset changed.

## Results

| Stage | Demo scale | 100x scale | Notes |
| --- | --- | --- | --- |
| Synthetic data generation (Python/Faker) | ~1s (7,755 rows) | **3m 25s** (770,205 rows) | This is the *fake-data generator's* cost, not the pipeline's — dominated by `Faker.unique.email()`, which gets slower as more unique values accumulate. Irrelevant once real customer data replaces synthetic generation. |
| `dbt seed` (CSV → DuckDB) | ~6s | **2m 3s** | This is dbt's own CSV-seed loader, which inserts row-by-row and is known to be slow at volume. **Not representative of the real ingestion path** — Airbyte bulk-loads into Snowflake natively; this number only exists because seeds are our zero-cost stand-in for Airbyte. |
| **`dbt build` (bronze→silver→gold→platinum transform + all tests)** | **4.56s** (72 checks) | **11.28s** (67 checks) | **This is the actual medallion architecture's performance.** 100x the data, ~2.5x the time — sub-linear, because DuckDB vectorizes and most of the fixed cost (dbt parsing, macro compilation, Python/JDBC overhead) doesn't scale with row count. |
| Correctness | straight_through_rate = 0.9047 | straight_through_rate = 0.9054 | Same metric, same logic, 100x the volume — matches within noise. All row counts (fct_orders=200,000, dim_customers=20,000, etc.) landed exactly as expected. |

## What this tells us

1. **The medallion transform itself is fast and scales well.** 11 seconds
   to rebuild bronze through platinum and run 67 tests against 770k rows,
   on a laptop, with DuckDB (a single-threaded-ish embedded engine, not even
   real distributed compute). At real Snowflake scale with a properly sized
   warehouse, this would be faster still for the same row count, and
   Snowflake's actual advantage shows up at row counts far beyond what's
   useful to test for free locally (tens/hundreds of millions of rows).
2. **The two slow numbers (Faker generation, dbt seed) are artifacts of
   how this pilot avoids paying for anything — not properties of the real
   pipeline.** A real customer's data doesn't need Faker to generate it,
   and Airbyte doesn't load CSVs via dbt's seed mechanism — it bulk-loads
   directly into Snowflake's native ingestion path, which is built for
   exactly this and doesn't have dbt-seed's row-by-row insert problem.
3. **Nothing here tests warehouse cold-start, concurrency, or incremental
   models** — this pipeline currently rebuilds every table fully on every
   run (`+materialized: table`/`view` throughout, no `incremental` models).
   That's fine at these row counts; at real production scale with daily
   syncs, moving `fct_orders`/`fct_support_tickets`/the platinum models to
   dbt's `incremental` materialization would matter far more than anything
   measured here, since it avoids re-scanning the full history every run.
4. **The L4-L11 reasoning chain remains the untested side** — this
   benchmark only covers L1-L3 (the medallion architecture itself). The
   open question from `docs/claimb-pilot-run.md` (per-layer LLM token cost)
   is unaffected by this result and still needs its own instrumentation.

## Reproducing this

```
cd data-source/generator
python generate_data.py --seed 7 --customers 20000 --products 200 \
  --orders 200000 --order-items 500000 --support-tickets 50000 \
  --output-dir /path/to/scratch/bench-data

# copy the CSVs into dbt/customer_platform/seeds/ as raw_*.csv (temporarily),
# then from dbt/customer_platform/:
DUCKDB_PATH=bench.duckdb dbt seed --target local --full-refresh
DUCKDB_PATH=bench.duckdb dbt build --target local --exclude "raw_customers raw_products raw_orders raw_order_items raw_support_tickets"
```
