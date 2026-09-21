---
name: ai-opportunity-assessment
description: Determines whether a diagnosed operational gap is suitable for an AI intervention, and at what autonomy level. Use after operational-diagnosis has produced DiagnosticRecords, or when asked whether AI is the right fix for a measured problem.
---

# L8 — AI Opportunity and Suitability

The guardrail against becoming an "LLM recommendation generator." Must be
able to return `NO_AI_RECOMMENDATION` when that's the honest answer — and
that outcome must be treated as a valid, successful result of this skill,
not a failure to route around.

## Assessment dimensions (score each 1-5, then judge)

repeatability, data availability, determinism, exception rate, judgment
intensity, error consequence, workflow integration, governance sensitivity,
evaluation measurability, existing automation.

## Autonomy levels

`ASSISTIVE` | `HUMAN_IN_LOOP` | `BOUNDED_AUTOMATION` | `AUTONOMOUS`

## Output: `AIOpportunityRecord`

Write `artifacts/ai_opportunities/<id>.json`:

```json
{
  "opportunity_id": "ticket-deflection-for-common-order-issues",
  "linked_metric_gaps": ["order_straight_through_rate:1"],
  "linked_diagnostics": ["exception_concentration_plan_tier"],
  "process_step": "post-order-completion support",
  "observed_problem": "<from the DiagnosticRecord, not restated as worse than measured>",
  "evidence_ids": ["<L6 evidence_id>"],
  "task_characteristics": {
    "repeatability": 4, "data_availability": 2, "determinism": 2,
    "exception_rate": 3, "judgment_intensity": 3, "error_consequence": 3,
    "workflow_integration": 2, "governance_sensitivity": 1
  },
  "ai_fit": "plausible_with_caveats",
  "readiness": "low -- no ticket free-text or category taxonomy beyond a single 'category' field exists in this synthetic dataset, which limits what an AI triage/deflection system could actually learn from",
  "risk_profile": "low (synthetic data, no real customer impact)",
  "autonomy_level": "HUMAN_IN_LOOP",
  "expected_kpi_impact": "directional only -- no baseline-vs-post-intervention data exists to estimate a number; do not fabricate a percentage lift",
  "dependencies": ["would need real ticket free-text and/or a finer category taxonomy to be actionable beyond this synthetic pilot"],
  "human_control_points": ["human review before any ticket auto-resolution"],
  "recommendation_confidence": "low"
}
```

## Steps

1. Read the `DiagnosticRecord`(s) from L7.
2. Score each task-characteristic dimension against what the data actually
   shows — not against what would be true of a generic "support tickets" problem.
3. If `data_availability` or `determinism` score low (as they will for this
   synthetic dataset's thin schema), let that honestly pull `readiness` down
   and consider returning `NO_AI_RECOMMENDATION` rather than inflating confidence.
4. Never state an `expected_kpi_impact` number without a measured baseline
   and a measured post-intervention comparison to derive it from.
5. Hand the record(s) to L9 (framework-benchmark-intelligence).
