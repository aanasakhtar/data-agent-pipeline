---
name: framework-benchmark-intelligence
description: Grounds a finding in approved frameworks and proposes an internal or external benchmark only if comparability requirements are met. Use after ai-opportunity-assessment, or when asked to benchmark a measured KPI against a comparable cohort.
---

# L9 — Benchmark and Framework Intelligence

Two separate claims must never be conflated: "cohort X performs at value V"
(factual, if measured) vs. "V is a valid target for this organization"
(requires comparability evidence). This skill is what's allowed to promote
the first into the second — and only when the checks below pass.

## Framework registry (this repo)

See `registry/framework_registry/` — currently seeded with one entry
(`ap-stp-analogy.json`) noting that this metric is modeled on the
Accounts-Payable Straight-Through-Processing pattern from the CLaiMB doc's
own worked example. No APQC PCF / SCOR DS / ISO 22400 content is loaded —
this is a placeholder, not a real framework mapping; say so rather than
inventing framework citations.

## Benchmark qualification checklist (all must pass to promote a cohort)

- cohort size >= `minimum_sample_guidance` from the MetricContract
- direction-aware statistic (higher-is-better -> upper-tail; lower-is-better -> lower-tail)
- stability across the time window (not a one-off spike)
- no confound (e.g. don't compare `enterprise` vs `free` tier as if they're
  operationally comparable without saying so)

## Output: `BenchmarkRecord` (or explicit suppression)

Write `artifacts/benchmarks/<id>.json`:

```json
{
  "metric_id": "order_straight_through_rate:1",
  "benchmark_source": "internal -- plan_tier cohort within this same synthetic dataset",
  "cohort_definition": "plan_tier = 'pro'",
  "cohort_count": "<actual count>",
  "cases_per_cohort": "<actual completed-order count in that cohort>",
  "direction": "higher_is_better",
  "statistic_used": "cohort mean (upper-tail cohort selected because higher-is-better)",
  "benchmark_value": "<actual value>",
  "stability": "not assessed -- single time window in this pilot, no trend data to test stability against",
  "comparability": "low confidence -- plan tiers likely differ in support entitlements, which confounds a straight comparison",
  "suppression_reason": "none -- but comparability caveat above is attached, not suppressed"
}
```

If qualification fails, write `suppression_reason` explaining why and do not
include a `benchmark_value` presented as a target.

## Steps

1. Read the `AIOpportunityRecord`/`DiagnosticRecord`/`EvidenceBundle` chain.
2. Check `registry/framework_registry/` for anything genuinely applicable —
   don't cite APQC/SCOR/ISO unless that registry actually contains a mapped entry.
3. Query DuckDB for the candidate cohort's value using the same
   numerator/denominator logic as the MetricContract, segmented.
4. Run the qualification checklist. If it fails, suppress with a reason.
5. Hand the result to L10 (verification-adversarial-review).
