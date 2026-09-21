# CLaiMB Pilot Run #1 — Order Straight-Through Rate

A real, end-to-end run of all 11 CLaiMB layers against this repo's local
DuckDB build (zero cost, no cloud accounts) — see `docs/local-testing.md`
for how the data got there and `docs/claimb-idea-fit.md` for why this
vertical-slice pilot was the recommended first step before building
anything further.

## What ran

1. `dbt seed --target local` + `dbt build --target local` — 72/72 tests
   passed. This is L1-L3 (Bronze/Silver/Gold), already built as this repo's
   medallion pipeline.
2. All 8 reasoning-layer skills (L4-L11) run in sequence for one metric:
   **order straight-through rate** (share of completed orders needing no
   support ticket) — chosen as the closest analog in this synthetic schema
   to the Accounts-Payable STP example in the CLaiMB doc.

## Result

**90.47%** of completed orders (873 of 965) needed no linked support ticket.
Segment breakdown: enterprise 93.55%, free 90.55%, pro 89.22%.

The diagnosis step (L7) correctly flagged the ~4-point pro-vs-enterprise
spread as **low-confidence, likely sampling noise** rather than presenting
it as a real pattern (the synthetic generator doesn't encode any tier-based
behavioral difference). The AI-opportunity step (L8) correctly returned
**`NO_AI_RECOMMENDATION`** as a result — there was no verified gap to act on.
The benchmark step (L9) correctly **suppressed** using the enterprise cohort
as a target for pro tier, because comparability wasn't established. The
verification step (L10) independently re-executed the evidence query in a
fresh DuckDB connection and got an exact match (965/873/0.9047) before
synthesis (L11) assembled the finding from verified numbers only.

Full artifact trail: `artifacts/business_context/order-fulfillment.json` →
`registry/metric_registry/order_straight_through_rate.json` →
`artifacts/evidence/order_straight_through_rate_20260918T161600Z.json` →
`artifacts/diagnostics/exception_concentration_plan_tier.json` →
`artifacts/ai_opportunities/order-fulfillment-ai-assessment.json` →
`artifacts/benchmarks/plan_tier_pro_cohort.json` →
`artifacts/verification/order_straight_through_rate_v1_verify.json` →
`artifacts/findings/order-straight-through-rate-pilot-1.{json,md}`.

## What this proves

- The **layer contracts hold together** end to end on real (if synthetic)
  data — each artifact schema from the CLaiMB doc was actually populated
  with real values, not placeholders, and the provenance chain is genuinely
  traceable file-to-file.
- The **suppression/refusal paths work**, and that's the most valuable
  result of this pilot: a naive implementation would be tempted to always
  produce a confident-sounding finding. This run shows the architecture's
  guardrails (hypothesis-labeling, `NO_AI_RECOMMENDATION`, benchmark
  suppression) actually firing on weak evidence instead of manufacturing a
  story — which is the entire point of the CLaiMB design (see the doc's
  section 2.1, principle 10: "Allow the system to say 'not measurable'...").
- The **local, zero-cost path is real** — no Snowflake/Airbyte/Neon account
  was touched. Everything above ran against a single `dev.duckdb` file.

## What this does *not* yet prove — and the open cost question still stands

This pilot was run as **one continuous reasoning pass**, not as 8 separate
agent invocations with independent context windows, retries, and tool calls.
That's the right way to validate the *logic* of the layer contracts cheaply,
but it does **not** answer the colleague's original question: what does
this cost per finding when L4-L11 are actually built as 8 separate
Claude Code skill invocations (or agents), each with its own context,
potentially retried by L10's verification loop?

To get a real answer, the next step (still local, still free) would be:

1. Actually invoke each of the 11 `.claude/skills/*` skills as **separate**
   Claude Code turns for this same metric (not one continuous pass), and
   record real token counts per turn from the session/transcript.
2. Deliberately introduce one bad artifact (e.g. hand-edit an EvidenceBundle
   to disagree with its MetricContract) and run L10 to confirm it rejects
   and retries, to measure the actual cost multiplier a rejection causes.
3. Multiply the measured per-layer token cost by the model pricing tier
   assumed for each layer (see `docs/claimb-idea-fit.md` section 3, point 2
   — not every layer needs frontier-tier reasoning).

That's a half-day exercise, not a rebuild, and it's the piece that turns
"the architecture works" (this pilot) into "here's what it costs" (the
open question).
