---
name: evidence-current-state
description: Executes an approved MetricContract against the local DuckDB Gold layer and produces an immutable EvidenceBundle. Use after kpi-metric-resolution has produced a MetricContract, or when asked to measure the current state of a defined KPI.
---

# L6 — Evidence and Current-State

Deterministic measurement only. This skill does not interpret the number —
it executes the contract's query exactly, checks data quality, and packages
the result. No narrative, no diagnosis.

## Output: `EvidenceBundle`

Write `artifacts/evidence/<metric_id>_<run_timestamp>.json`:

```json
{
  "evidence_id": "order_straight_through_rate_20260918T000000Z",
  "metric_contract_id": "order_straight_through_rate:1",
  "observed_value": 0.0,
  "period": "2022-01-01 to 2026-09-08",
  "sample_size": 0,
  "distribution_summary": {"by_plan_tier": {}, "by_country": {}},
  "trend_summary": "not computed in this run -- single-period snapshot",
  "segment_results": [],
  "source_objects": ["fct_orders", "fct_support_tickets"],
  "query": "<the exact SQL executed, copied from executable_query_template>",
  "query_hash": "<sha256 of the exact query text>",
  "execution_timestamp": "<ISO 8601>",
  "data_quality_status": "HIGH",
  "freshness_status": "current -- ran against the same dbt build used for L1-L3",
  "source_coverage": "100% -- all 2000 orders in fct_orders considered",
  "caveats": [],
  "provenance_chain": ["MetricContract order_straight_through_rate v1", "artifacts/gold/manifest.json"]
}
```

## Evidence confidence rubric (assign `data_quality_status`)

- **HIGH**: sample_size meets `minimum_sample_guidance`, source_coverage 100%,
  no failing dbt tests on the relevant Silver/Gold tables.
- **MEDIUM**: sample size below guidance but > 20, or minor coverage gaps.
- **LOW**: sample size very small, or relevant dbt tests are failing.
- **UNUSABLE**: query cannot run (missing table/column), or result is
  nonsensical (e.g. negative rate) -- do not pass an UNUSABLE bundle forward
  to L7; report the failure back to L5 instead.

## Steps

1. Read the `MetricContract` from `artifacts/metric_contracts/`.
2. Check `registry/verified_queries/<metric_id>.yml` (borrowed from Cortex
   Analyst's Verified Query Repository — see `docs/competitive-landscape.md`).
   If a verified entry already answers this exact question, prefer its `sql`
   over re-deriving `executable_query_template` from scratch — it's already
   been through L10 once. Still re-execute it fresh each run (this skill
   measures current state, it doesn't just replay a cached number), but
   don't silently diverge from the verified SQL without a reason.
4. Run the query (verified or newly derived) against the local DuckDB file
   (`dbt/customer_platform/dev.duckdb`) — e.g. via
   `python -c "import duckdb; print(duckdb.connect('dbt/customer_platform/dev.duckdb').sql('<query>'))"`,
   adjusting schema-qualified table names to whatever `dbt build --target local`
   actually created (check with `dbt list --target local` or query
   `information_schema.tables` if unsure).
5. Compute `sample_size` (the denominator's row count) and any segment
   breakdowns named in the contract's `dimensions`.
6. Check the corresponding dbt test results (`dbt test --target local`) for
   the tables involved; factor failures into `data_quality_status`.
7. Hash the exact query text (`query_hash`) so L10 can re-execute the same
   query independently later and compare.
8. Write the `EvidenceBundle`. If this query wasn't already in
   `registry/verified_queries/`, flag it for L10 to add once verified.
   Hand the bundle to L7 (operational-diagnosis).
