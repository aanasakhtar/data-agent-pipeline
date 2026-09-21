---
name: gold-normalize-model
description: Builds canonical business entities and metric facts from Silver data. Use after Silver has run, or when asked to check the Gold/business semantic layer for the customer_platform pipeline.
---

# L3 — Gold: Semantic Business Model

Local-testing note: Gold is `dbt/customer_platform/models/marts/core/`
(dims/facts) plus `models/marts/platinum/` (pre-aggregated metric facts,
CLaiMB folds these into Gold — this repo keeps them as a separate layer,
see `docs/decisions.md` item D / `docs/architecture.md`).

## Gold boundary (important)

Gold answers: *"What does the customer's operational data look like in
business terms?"* It does **not** decide whether a gap matters or whether AI
is the answer — that starts at L4. Do not let this skill produce
recommendations; it only produces `gold_*` structures.

## Standard outputs (mapped to this repo)

| CLaiMB concept | This repo |
| --- | --- |
| `gold_canonical_events` | `fct_orders`, `fct_support_tickets` (event-like facts) |
| `gold_case_traces` | `int_customer_orders` (customer_order_sequence gives a light case trace) |
| `gold_metric_facts` | `customer_360`, `weekly_business_metrics` |
| `gold_actor_activity` | not modeled in this synthetic dataset (no employee/agent actor table) — report as unavailable, don't invent one |
| `gold_text_profiles` | not modeled (no free-text ticket bodies in the synthetic data) — report as unavailable |

## Invariants

- Report `gold_actor_activity` and `gold_text_profiles` as **unavailable**
  rather than fabricating data — the synthetic schema genuinely has no actor
  or free-text fields. This is a real limitation to flag to L4-L8, not paper over.

## Output: `GoldSemanticModel` manifest

Write `artifacts/gold/manifest.json`:

```json
{
  "gold_canonical_events": ["fct_orders", "fct_support_tickets"],
  "gold_case_traces": ["int_customer_orders"],
  "gold_metric_facts": ["customer_360", "weekly_business_metrics"],
  "gold_actor_activity": "unavailable - no actor/agent entity in synthetic schema",
  "gold_text_profiles": "unavailable - no free-text fields in synthetic schema",
  "row_counts": {"fct_orders": 2000, "fct_support_tickets": 500, "customer_360": 200}
}
```

## Steps

1. `cd dbt/customer_platform && dbt build --target local --select marts+`
2. Query DuckDB for row counts of each Gold/Platinum table.
3. Write `artifacts/gold/manifest.json` as above, with real counts substituted.
