---
name: operational-diagnosis
description: Analyzes an EvidenceBundle and Gold process traces to explain observed operational patterns behind a measured gap. Use after evidence-current-state has produced an EvidenceBundle, or when asked why a measured KPI is at its current level.
---

# L7 — Process and Gap Diagnosis

The critical discipline here: **separate observation from explanation**.
"18% of completed orders have a linked ticket" is measurable. "Poor product
descriptions cause those tickets" is a hypothesis and must be labeled as one.

## Diagnostic library (use what the synthetic schema can actually support)

| Diagnostic family | Available in this dataset? | Evidence pattern |
| --- | --- | --- |
| Exception concentration | Yes | Are tickets/no-STP concentrated in specific `plan_tier`, `country`, or `product_category`? (`customer_360`, `fct_support_tickets` joined to `dim_products` via `order_items`) |
| Manual burden / rework | Partial | `int_order_items_enriched.price_variance != 0` is the closest proxy to "rework"/pricing exceptions in this schema |
| Handoffs | No | No actor/team entity exists (see L3's `gold_actor_activity: unavailable`) — do not fabricate a handoff diagnosis |
| Cycle/wait time | Partial | `fct_support_tickets.resolution_hours` measures ticket resolution wait, not order cycle time (no order-stage timestamps beyond order_date/created_at/updated_at exist) |
| Unstructured work / text burden | No | No free-text fields in the synthetic schema — do not fabricate this |

Report the "No" rows as **not diagnosable with this dataset**, don't skip
them silently — CLaiMB's own invariant #8 ("no source failure may disappear
silently") applies here too.

## Output: `DiagnosticRecord`

Write `artifacts/diagnostics/<id>.json`, one per diagnostic finding:

```json
{
  "diagnostic_id": "exception_concentration_plan_tier",
  "category": "exception_concentration",
  "observation": "<measured, e.g. 'enterprise-tier customers account for X% of completed orders but Y% of orders-with-tickets'>",
  "interpretation": "<explicitly labeled as hypothesis if not directly measured>",
  "evidence_ids": ["order_straight_through_rate_<timestamp>"],
  "source_queries": ["<the segment-breakdown SQL actually run>"],
  "affected_process_steps": ["order fulfillment", "post-completion support"],
  "affected_segments": ["plan_tier=enterprise"],
  "severity": "medium",
  "confidence": "medium",
  "causal_status": "observed"
}
```

`causal_status` must be one of: `observed`, `hypothesis`, `supported`,
`unverified`. Never write `observed` for something that wasn't directly
queried.

## Steps

1. Read the `EvidenceBundle` from L6.
2. For each diagnostic family marked "Yes"/"Partial" above, run the actual
   segment-breakdown query against DuckDB (group the numerator/denominator by
   `plan_tier`, `country`, `product_category`, etc.).
3. Write one `DiagnosticRecord` per pattern actually found — skip families
   with no signal rather than forcing a finding.
4. Explicitly record the "No" families as not diagnosable, with the reason.
5. Hand all records to L8 (ai-opportunity-assessment).
