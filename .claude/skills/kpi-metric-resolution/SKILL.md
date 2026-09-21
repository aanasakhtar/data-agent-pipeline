---
name: kpi-metric-resolution
description: Resolves a BusinessFunctionContext into an explicit, versioned, executable MetricContract. Use after intent-business-scope has run, or when asked to define/formalize a KPI for the customer_platform data.
---

# L5 — KPI / Metric Resolution

This is the semantic control point. A goal like "reduce tickets on completed
orders" is an intention, not a measurable spec. This skill converts it into a
formal `MetricContract` — mandatory before any current-state measurement (L6).

## Non-negotiable invariants

1. No headline KPI without an accepted `MetricContract`.
2. The contract must specify its denominator explicitly.
3. The contract must specify its grain explicitly.
4. Direction (higher-is-better / lower-is-better) must be explicit.
5. A metric with unresolved semantic ambiguity cannot become a headline
   result — resolve it here (pick a definition and record it as an
   assumption) or escalate it back to L4's `unresolved_questions`, don't
   pass ambiguity downstream silently.
6. The executable query must match the contract's numerator/denominator —
   check this before writing the contract, not after L6 runs it.
7. **Resolve terms through `registry/semantic_model.yml` first** — check
   `metrics:` for an existing standardized definition before writing a new
   numerator/denominator from scratch, and express `numerator_definition`/
   `denominator_definition` in terms of the semantic model's logical
   objects (`Customer`, `Order`, `SupportTicket`) and their relationships
   from `registry/ontology_objects.yml`, not by inventing a join against
   raw table names. This is the Wren AI MDL / Palantir Ontology discipline
   — see `docs/competitive-landscape.md`. If a metric needs a relationship
   that isn't in `ontology_objects.yml`, that file is out of date; fix it
   there, don't route around it.

## Output: `MetricContract`

Write `registry/metric_registry/<metric_id>.json` (the registry is the
durable copy; also copy it to `artifacts/metric_contracts/<metric_id>.json`
for this run):

```json
{
  "metric_id": "order_straight_through_rate",
  "version": 1,
  "business_process": "Order Fulfillment & Support",
  "metric_name": "Order Straight-Through Rate",
  "user_goal_text": "Reduce the share of completed orders that generate a support ticket",
  "semantic_definition": "Share of completed orders with zero linked support tickets, over all completed orders",
  "direction": "higher_is_better",
  "numerator_definition": "count(distinct fct_orders.order_id) where order_status = 'completed' and order_id not in (select order_id from fct_support_tickets where order_id is not null)",
  "denominator_definition": "count(distinct fct_orders.order_id) where order_status = 'completed'",
  "grain": "one row per period (this run: single value over the full dataset window)",
  "unit": "percent",
  "time_window": "2022-01-01 to 2026-09-08 (var synthetic_data_as_of)",
  "inclusion_rules": ["order_status = 'completed'"],
  "exclusion_rules": ["orders with status pending/cancelled/refunded are excluded from both numerator and denominator"],
  "dimensions": ["plan_tier", "country"],
  "target_value": null,
  "target_source": "not specified by customer -- see L4 unresolved_questions",
  "source_entities": ["fct_orders", "fct_support_tickets"],
  "gold_fields": ["fct_orders.order_id", "fct_orders.order_status", "fct_support_tickets.order_id"],
  "executable_query_template": "select count(distinct o.order_id) filter (where t.order_id is null) * 1.0 / count(distinct o.order_id) as straight_through_rate from fct_orders o left join fct_support_tickets t on o.order_id = t.order_id where o.order_status = 'completed'",
  "expected_result_shape": "single row, one float column 0.0-1.0",
  "data_quality_requirements": ["fct_orders.order_id not null and unique", "fct_support_tickets.order_id may be null (ticket not linked to an order)"],
  "minimum_sample_guidance": "at least 50 completed orders for the rate to be reportable at HIGH confidence",
  "framework_references": ["Analogous to Accounts-Payable Straight-Through Processing (STP) -- see CLaiMB_Data_Agent_Full_Multilayered_Architecture.md section 11"],
  "provenance": "Derived from BusinessFunctionContext at artifacts/business_context/order-fulfillment.json"
}
```

## Steps

1. Read the `BusinessFunctionContext` from L4.
2. Check `registry/metric_registry/` for an existing contract for this goal,
   **and** `registry/semantic_model.yml`'s `metrics:` section for an already
   standardized definition, before writing a new one.
3. Write the numerator/denominator/grain/direction explicitly, in terms of
   the semantic model's logical objects/fields — if any of these can't be
   stated precisely because a term is missing from `semantic_model.yml`,
   that's a signal to extend the semantic model (or go back to L4), not to
   write a vague contract with an ad hoc join.
4. Check `registry/verified_queries/` for an existing verified SQL pair
   answering this same question — if one exists, reuse its `sql` as the
   contract's `executable_query_template` rather than re-deriving it (this
   is Cortex Analyst's verified-query pattern; see
   `docs/competitive-landscape.md`). If none exists yet, write one after L10
   verifies the new query, so the next run of this metric can reuse it.
5. Validate: does `gold_fields` actually exist in `artifacts/gold/manifest.json`?
   If not, the contract is not executable — fix it before handing to L6.
6. Save to both `registry/metric_registry/` (durable) and
   `artifacts/metric_contracts/` (this run's copy).
