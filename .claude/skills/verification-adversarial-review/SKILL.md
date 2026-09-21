---
name: verification-adversarial-review
description: Independently attempts to falsify every material claim (MetricContract, EvidenceBundle, DiagnosticRecord, AIOpportunityRecord, BenchmarkRecord) before synthesis. Use as the last step before executive-synthesis, or when asked to verify/audit a finding's evidence chain.
---

# L10 — Independent Verification (the trust boundary)

This is the layer most likely to dominate cost and latency in the full
chain — see `docs/claimb-idea-fit.md` section 3. Its job is not to ask "does
this sound right" but to independently re-derive or falsify each claim.

## Verification engines (run all that apply)

1. **Semantic check** — does the `EvidenceBundle.query` actually match the
   `MetricContract`'s numerator/denominator definitions? Read both, compare
   by hand.
2. **Query re-execution** — re-run the exact query from `query_hash`
   independently (fresh DuckDB connection) and confirm the value matches
   `observed_value` exactly.
3. **Arithmetic check** — recompute any derived percentages/rates from the
   raw counts; don't trust the upstream layer's arithmetic.
4. **Data quality check** — does `data_quality_status` in the EvidenceBundle
   match what re-running the relevant dbt tests actually shows right now?
5. **Benchmark check** — did L9's qualification checklist actually pass, or
   was a benchmark presented despite a suppression reason?
6. **Contradiction check** — do any two records in this chain disagree (e.g.
   L7 says "observed" for something L6's evidence doesn't actually show)?
7. **Provenance check** — does every number trace back through
   evidence_ids/metric_contract_id to a real artifact file that exists?
8. **Narrative integrity** — (checked again after L11 runs) did synthesis
   change any verified number?

## Outcomes

`PASS` | `LOW_CONFIDENCE` | `REJECT` | `UNVERIFIABLE_NEEDS_HUMAN_REVIEW`

## Rejection loop

`REJECT` -> state the exact failed invariant -> route back to the specific
producing layer (not a blanket redo) -> max **2** retries -> if still
failing, escalate to `UNVERIFIABLE_NEEDS_HUMAN_REVIEW`. Never convert a
repeated failure into a guessed PASS.

## Output: `VerificationResult`

Write `artifacts/verification/<id>.json`:

```json
{
  "verification_id": "order_straight_through_rate_v1_verify",
  "checked_records": ["MetricContract order_straight_through_rate:1", "EvidenceBundle <id>", "DiagnosticRecord exception_concentration_plan_tier", "AIOpportunityRecord ticket-deflection-for-common-order-issues", "BenchmarkRecord <id>"],
  "engine_results": {
    "semantic_check": "PASS",
    "query_reexecution": "PASS -- re-ran independently, value matched to 4 decimal places",
    "arithmetic_check": "PASS",
    "data_quality_check": "PASS",
    "benchmark_check": "PASS -- comparability caveat correctly attached, not suppressed inappropriately",
    "contradiction_check": "PASS",
    "provenance_check": "PASS -- all referenced artifact files exist"
  },
  "disposition": "PASS",
  "retry_count": 0,
  "notes": "First pass, no rejections needed for this pilot run."
}
```

## Steps (for real, not just templated)

1. Open every upstream artifact file referenced by evidence_ids/provenance
   chains — actually read them, don't assume they say what the record claims.
2. Re-run the L6 query yourself, independently, and diff the result against
   `observed_value`.
3. Recompute any percentage by hand from the raw numerator/denominator.
4. If anything fails, write `disposition: REJECT` with the exact engine and
   reason, and say which upstream skill needs to re-run — don't silently fix
   it yourself, that defeats the point of independent verification.
5. Hand a `PASS` or `LOW_CONFIDENCE` result to L11. A `REJECT` or
   `UNVERIFIABLE` result does not proceed to synthesis.
6. On `PASS`: if this query isn't already in `registry/verified_queries/`,
   add it now (name/question/sql/verified_at/verified_by/verified_result,
   in the Cortex-Analyst-style format — see
   `registry/verified_queries/order_straight_through_rate.yml` for the
   pattern). This is what makes verification pay off on future runs: the
   next time L6 measures this same metric, it starts from an
   already-trusted query instead of re-deriving and re-verifying from zero.
   Never add an entry on anything less than `PASS`.
