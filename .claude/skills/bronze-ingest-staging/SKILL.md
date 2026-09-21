---
name: bronze-ingest-staging
description: Introspects the customer_platform data sources and stages raw data into an immutable Bronze landing zone. Use when starting a new CLaiMB analysis, refreshing source data, or when asked to run/check the Bronze layer.
---

# L1 — Bronze: Raw Ingestion and Staging

Local-testing note: in this repo, "ingestion" is already done for you by
`dbt seed` (loads `dbt/customer_platform/seeds/raw_*.csv` into DuckDB) --
that's the zero-cost stand-in for Airbyte landing data into Snowflake's `RAW`
schema. This skill's job is to run that, verify it, and emit a manifest —
not to reinvent ingestion.

## Responsibilities

1. Discover scoped sources: the 5 tables in `data-source/schema.sql`
   (customers, products, orders, order_items, support_tickets).
2. Load them without transformation: `dbt seed --target local` (from
   `dbt/customer_platform/`), or confirm they're already loaded.
3. Reconcile source and landed record counts (compare CSV row counts in
   `data-source/generator/output/*.csv` against what landed in DuckDB).
4. Emit a `BronzeArtifactManifest` per table to `artifacts/bronze/`.

## Invariants

- Zero business transformation at this layer — no filtering, renaming, or
  type casting here (that's Silver's job, in `models/staging/`).
- No silent source omission — if a table failed to load, say so explicitly
  in the manifest rather than skipping it.
- Every artifact has lineage back to its source file/table and load time.

## Output: `BronzeArtifactManifest`

Write one JSON file per table to `artifacts/bronze/<table>.json`:

```json
{
  "source_id": "customer_platform_synthetic",
  "object_id": "customers",
  "snapshot_id": "<dbt seed run timestamp>",
  "row_count": 200,
  "schema_fingerprint": "<column names + types, e.g. from `duckdb -c \"describe raw_customers\"`>",
  "ingested_at": "<ISO 8601 timestamp>",
  "source_status": "OK",
  "quarantine_reason": null,
  "lineage": "data-source/generator/output/customers.csv -> dbt seed -> DuckDB main.raw_customers"
}
```

## Steps

1. `cd dbt/customer_platform && dbt seed --target local`
2. For each of the 5 tables, query DuckDB (`python -c "import duckdb; print(duckdb.connect('dev.duckdb').sql('select count(*) from main.raw_customers'))"` or the `duckdb` CLI if installed) to get the landed row count.
3. Compare against the row count printed by `generate_data.py` / the CSV line count.
4. Write the manifest JSON for each table to `artifacts/bronze/`.
5. If any table's counts don't match or the seed failed, set `source_status`
   to `"FAILED"` with a `quarantine_reason`, and say so plainly rather than
   continuing as if ingestion succeeded.
