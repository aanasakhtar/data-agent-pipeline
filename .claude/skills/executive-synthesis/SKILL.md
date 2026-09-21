---
name: executive-synthesis
description: Converts verified records into a customer-facing finding, without touching source data or mutating any verified number. Use as the final step after verification-adversarial-review has returned PASS or LOW_CONFIDENCE.
---

# L11 — Executive Synthesis

Deliberately the thinnest layer. Assembles, does not calculate.

## Invariants

- No source-data access — read only the verified artifact JSON files, never
  query DuckDB directly from this skill.
- No Gold access.
- No numeric mutation — every number in the finding must be copied verbatim
  from a `PASS`/`LOW_CONFIDENCE`-verified artifact, not recomputed here.
- No unsupported factual claims — if it's not in an upstream artifact, it
  doesn't go in the finding.
- Directional evidence stays explicitly directional in the write-up (don't
  upgrade a `LOW_CONFIDENCE` number to sound definitive).
- Only accepts input whose `VerificationResult.disposition` is `PASS` or
  `LOW_CONFIDENCE` — refuse to synthesize a `REJECT`ed chain.

## Output: `FindingDraft`

Write `artifacts/findings/<id>.json` plus a short human-readable `.md` next to it:

```json
{
  "finding_id": "order-straight-through-rate-pilot-1",
  "headline": "<one sentence, numbers copied verbatim from evidence>",
  "severity": "<from the diagnostic/opportunity records, not invented here>",
  "verified_metrics": ["<observed_value from the EvidenceBundle, with its evidence_id>"],
  "linked_evidence": ["<evidence_id>"],
  "diagnosis": ["<diagnostic_id list>"],
  "benchmark_context": "<BenchmarkRecord id, with its comparability caveat carried over verbatim>",
  "ai_opportunity": "<AIOpportunityRecord id and its autonomy_level/readiness, or NO_AI_RECOMMENDATION>",
  "advisory_match": "not applicable -- no advisory_catalog populated in this pilot (registry/advisory_catalog/ is empty)",
  "verification_status": "<VerificationResult.disposition>",
  "confidence": "<carried over from the weakest link in the chain, not the strongest>",
  "provenance_chain": ["business_context -> metric_contract -> evidence -> diagnosis -> ai_opportunity -> benchmark -> verification -> this finding"]
}
```

## Steps

1. Read the `VerificationResult`. If not `PASS`/`LOW_CONFIDENCE`, stop —
   report why, don't produce a finding anyway.
2. Read each upstream artifact named in `checked_records`.
3. Assemble the `FindingDraft` JSON, copying numbers verbatim.
4. Write a short markdown version for human reading (a few paragraphs or a
   bulleted list, not a full report, per the `weekly-report` skill's tone
   guidance).
5. This is the end of the chain for one metric. Report the full path
   (artifacts/business_context -> ... -> findings) so it can be audited.
