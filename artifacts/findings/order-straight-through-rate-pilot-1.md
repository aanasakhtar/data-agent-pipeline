# Finding: Order Straight-Through Rate

**Headline:** 90.47% of completed orders (873 of 965) required no support
ticket. No target was given by the customer, so this is reported as a
measured baseline rather than a gap against a goal.

**What we found:** Straight-through rate varies slightly by plan tier
(enterprise 93.55%, free 90.55%, pro 89.22%), but this ~4-point spread is
flagged by the diagnosis step as **low-confidence, likely noise** — the
synthetic data generator doesn't encode any real tier-based behavioral
difference, so this isn't presented as a discovered business insight.

**AI recommendation:** None. The pipeline correctly returned
`NO_AI_RECOMMENDATION` because there's no verified gap to address — this is
the intended behavior (see `.claude/skills/ai-opportunity-assessment/SKILL.md`),
not a failure of the pipeline.

**Verification:** PASS. The evidence query was independently re-executed in a
fresh DuckDB connection and matched the reported value exactly (965/873/0.9047),
and the arithmetic was recomputed by hand from the raw counts.

**Full provenance chain:** business_context → metric_contract → evidence →
diagnosis → ai_opportunity → benchmark → verification → this finding. Every
file is under `artifacts/` in this repo and can be opened directly.
