---
name: intent-business-scope
description: Resolves the analytical scope of a business goal into a BusinessFunctionContext before any KPI or evidence work happens. Use when a user states a business goal or question about the customer_platform data (e.g. "why is churn high", "are we straight-through processing orders") and no MetricContract exists yet for it.
---

# L4 — Business Intent and Scope

This is the first reasoning-layer skill (start of the "8-stage chain":
L4-L11). It receives a stated business goal and turns it into an explicit,
bounded `BusinessFunctionContext` — it does **not** calculate anything.

## Invariants

- Preserve the customer's stated current state verbatim — don't round it off.
- Explicitly identify the process and objective in scope.
- Do not invent a KPI definition here — that's L5's job. If the goal implies
  a metric, name it in `unresolved_questions`, don't define it.
- Carry unresolved ambiguity forward rather than silently resolving it.

## Output: `BusinessFunctionContext`

Write `artifacts/business_context/<slug>.json`:

```json
{
  "business_function": "Order Fulfillment & Support",
  "use_case": "Reduce the share of completed orders that generate a support ticket",
  "process_scope": "Order lifecycle from order_date to completed status, and any linked support_tickets",
  "customer_goal": ["Increase straight-through order completion (no ticket needed)"],
  "stated_current_state": "Unknown -- not yet measured; goal was stated qualitatively",
  "desired_target": ["Not yet specified by customer -- flag as unresolved"],
  "time_horizon": "Trailing full dataset (2022-01-01 through 2026-09-08, see synthetic_data_as_of var)",
  "organizational_scope": "All customers, all plan tiers",
  "constraints": ["Synthetic data -- no real customer PII, findings are for pipeline-testing only"],
  "authorized_sources": ["fct_orders", "fct_support_tickets", "dim_customers", "customer_360"],
  "unresolved_questions": [
    "Exact target % for straight-through rate not given by user -- ask, or proceed evidence-first and let the customer react to the measured baseline",
    "Definition of 'generates a ticket' -- any ticket linked to the order, or only tickets opened before order completion? Default to any-linked-ticket unless told otherwise, and record that assumption in the MetricContract."
  ]
}
```

## Steps

1. Read the user's stated goal/question verbatim.
2. Identify which Gold/Platinum tables (from `artifacts/gold/manifest.json`)
   are relevant — don't scope in tables that don't exist in this dataset.
3. List what's actually unresolved (a real target number, an ambiguous
   definition) rather than guessing and presenting a guess as settled.
4. Write the `BusinessFunctionContext` JSON. Hand it to L5 (kpi-metric-resolution).
