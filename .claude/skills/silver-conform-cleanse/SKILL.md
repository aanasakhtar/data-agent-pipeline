---
name: silver-conform-cleanse
description: Converts Bronze artifacts into typed, conformed, quality-profiled Silver entities. Use after Bronze has run, or when asked to check data quality / conformance for the customer_platform pipeline.
---

# L2 — Silver: Conformance, Cleansing and Quality

Local-testing note: in this repo, Silver is `dbt/customer_platform/models/intermediate/`
and `snapshots/customers_snapshot.sql` (SCD2 on `plan_tier`/`status`). This
skill's job is to run those, then produce the quality-profile artifact CLaiMB
expects — the transformation logic itself already exists as dbt models.

## Responsibilities

- Type normalization (already encoded as `::type` casts in `models/staging/`,
  which effectively straddles Bronze/Silver here — see `docs/architecture.md`
  for how this repo's layering maps to CLaiMB's).
- Entity normalization: `int_customer_orders`, `int_order_items_enriched`.
- Change tracking / "dedup via history": `customers_snapshot` (dbt snapshot,
  check strategy on `plan_tier`/`status`).
- Quality profiling: null rate, duplicate rate, freshness — **not currently
  computed automatically**; this skill computes it.

## Invariants

- Transformations must be explicit — point to the actual `.sql` file that
  performs each one, don't describe a transformation that isn't in the repo.
- Missing values must not be silently imputed as business truth — if a field
  is null, report the null rate; don't fabricate a value.
- Quality metrics become part of downstream evidence confidence (L6 reads
  this artifact's quality scores when deciding `HIGH`/`MEDIUM`/`LOW`/`UNUSABLE`).

## Output: `SilverEntity`

Write one JSON file per intermediate model/snapshot to `artifacts/silver/`:

```json
{
  "entity_name": "int_customer_orders",
  "source_objects": ["stg_orders", "stg_customers"],
  "transformation_rules": "models/intermediate/int_customer_orders.sql",
  "null_rates": {"customer_status": 0.0, "days_since_signup": 0.0},
  "duplicate_rate": 0.0,
  "schema_drift": "none detected",
  "freshness": "<latest order_date in the dataset>",
  "lineage": "stg_orders + stg_customers -> int_customer_orders"
}
```

## Steps

1. `cd dbt/customer_platform && dbt build --target local --select staging+ intermediate+ customers_snapshot`
2. `dbt test --target local --select staging+ intermediate+` and record any
   failing tests as a quality signal (a failing `not_null`/`unique` test here
   should push that entity's confidence toward `LOW` at L6, not be silently ignored).
3. Query DuckDB for null rates on key columns per table (e.g.
   `select count(*) - count(csat_score) as nulls, count(*) as total from main.silver.int_... ` —
   adjust schema/table names to what actually landed).
4. Write one `SilverEntity` JSON per model to `artifacts/silver/`.
