# CLaiMB Data Agent — Idea Fit Assessment

Working notes comparing the colleague's CLaiMB 11-layer architecture proposal
against what this repo already builds, plus a direct answer to the open
question: **has the per-finding cost of the 8-stage reasoning chain been
priced out?** (Short answer: no, and it should be before any of L4-L11 gets built.)

Source doc: `CLaiMB_Data_Agent_Full_Multilayered_Architecture.md` (colleague's research, shared 2026-09-18).

## 1. What CLaiMB proposes, in one pass

11 layers, two sections:

- **Data Foundation (L1-L3):** Bronze (raw/immutable) → Silver (conformed/typed/quality-scored)
  → Gold (canonical business entities, process traces, metric facts).
- **Intelligence & Trust Plane (L4-L11), the "8-stage reasoning chain":**
  L4 Intent & Scope → L5 KPI/Metric Resolution → L6 Evidence/Current-State →
  L7 Diagnosis → L8 AI Opportunity → L9 Benchmark/Framework → L10 Verification →
  L11 Executive Synthesis.

Each of L4-L11 gets its own `SKILL.md`, its own allowed-tools list, its own
input/output contract (`MetricContract`, `EvidenceBundle`, `DiagnosticRecord`,
`AIOpportunityRecord`, `BenchmarkRecord`, `VerifiedFindingRecord`), and a
verification gate (L10) that can reject and force a bounded retry (max 2) back
into the producing layer before escalating to human review.

## 2. Fit against this repo

This repo (`workflow.md` + the hands-on build under `dbt/customer_platform/`)
is a working instance of exactly the Data Foundation half of CLaiMB:

| CLaiMB layer | This repo's equivalent | Fit |
| --- | --- | --- |
| L1 Bronze | `models/staging/` (bronze schema), fed by Airbyte into `RAW` | Direct match — immutable-ish landing + light typing, no business logic |
| L2 Silver | `models/intermediate/` + `snapshots/customers_snapshot.sql` (SCD2) | Direct match — conformance, dedup via snapshot, typed entities |
| L3 Gold | `models/marts/core/` (dims/facts) + `models/marts/platinum/` (metric facts) | Close match — CLaiMB folds "metric facts" into Gold; we split a further `platinum` layer out for pre-aggregated, consumer-ready tables. Cosmetic naming difference, not a structural one. |
| L4-L11 | **Not built.** `gate-hook.py` (hard approval gating) is the only piece of workflow.md that rhymes with L10's verification gate, and even that isn't implemented yet (see `docs/decisions.md` item I). | No equivalent exists yet |

**Conclusion on fit:** the medallion pipeline we already have hands-on is
directly reusable as CLaiMB's Data Foundation — it's the same architecture,
same layer boundaries, same "no business judgment in Gold" rule. The
colleague's new material is entirely L4-L11. That's the part with no
precedent in what we've built, and it's also the part that is expensive,
ambiguous, and easy to over-build.

## 3. On the colleague's cost question — this is the right question to ask first

Quoting the ask: *"whether we have priced out what an 8-stage reasoning chain
costs per finding... before committing to building all of it."* Agreed, and
not just as due diligence — the architecture doc itself gives reasons to
expect this cost is **non-linear**, not just "8 stages × 1 LLM call":

1. **The verification loop multiplies cost, not adds to it.** L10 can reject
   and send a *targeted retry* back to the producing layer, up to 2 times,
   before escalating. A rejected `EvidenceBundle` doesn't just cost another
   L10 pass — it re-runs L6 (which may re-run a Snowflake query), potentially
   invalidates L7/L8/L9 records that depended on it, and re-triggers their
   verification too. Worst case for one finding is closer to 8 stages × 3
   attempts × downstream re-verification, not 8 flat calls.

2. **Not every layer needs the same model tier, and the doc doesn't say so
   explicitly.** L1-L3 should be near-zero LLM cost — they're the same
   deterministic dbt/SQL work as this repo's medallion layer, with maybe one
   LLM-assisted schema-mapping step in Silver. L4 (Intent) and L5 (KPI
   Resolution) are semantic-matching against a registry — plausibly a
   cheaper/faster model. L7 (Diagnosis), L8 (AI Opportunity), and L10
   (Verification/adversarial review) are where real reasoning happens and a
   frontier-tier model is probably justified. Pricing this with one flat
   "$X per LLM call × 8" assumption will be wrong in both directions —
   understating the expensive stages and overstating the cheap ones.

3. **Cost per finding isn't the only number that matters — volume is.** The
   real business question is `cost_per_finding × findings_per_customer_per_period
   × customers`, compared against what a finding is worth (advisory
   engagement value, or whatever CLaiMB monetizes on). An $8 finding is fine
   at 50 findings/month; the same $8 is a different conversation at 5,000/month.

4. **Verification's own cost is oddly the one most worth measuring first.**
   It re-executes queries independently, recomputes arithmetic, and does an
   adversarial semantic pass — the doc frames it as the trust boundary, which
   is right, but that also makes it the stage most likely to dominate the
   cost/latency budget. If verification alone is expensive, that's useful to
   know before designing L4-L9 around producing candidates for it to check.

### Recommendation: cost one vertical slice before building all 11 skills

Concretely: take the AP example from section 11 of the doc (straight-through
processing gap), build the minimum real path through **all 11 layers** for
that one metric with real (or realistic synthetic) data, and instrument every
LLM call with input/output tokens and model used. That gives:

- A real, not estimated, `cost_per_finding` for at least one case shape.
- A breakdown by layer, so it's visible which stages are cheap/deterministic
  (likely L1-L3, matching this repo) vs. which are LLM-heavy (likely
  L7/L8/L10).
- A measured retry rate for L10, instead of assuming the "max 2 retries"
  ceiling is either rarely or always hit.
- A number to multiply by expected findings volume before deciding to build
  out the remaining 10 skill files, the registries (`metric_registry`,
  `framework_registry`, `advisory_catalog`, etc.), and the orchestrator state
  machine described in sections 13-14.

This is a small build relative to the full 11-layer system (one metric, one
path, no registry infrastructure, no golden eval set yet) and it directly
answers the open question instead of estimating around it.

## 4. Other things worth flagging while reading the doc closely

- **Section 15 (Context Isolation Policy)** is doing real architectural work
  and shouldn't be treated as a nice-to-have — it's what makes the
  "synthesis never touches raw data" and "verifier has no access to producer
  reasoning traces" guarantees actually enforceable rather than just written
  in a prompt. Worth deciding early whether this is enforced via tool
  allowlists (as the doc suggests) or something stronger (separate
  agent/service identities), since retrofitting isolation after the skills
  exist is much harder than designing for it from L4 onward.
- **The `NO_AI_RECOMMENDATION` / "not measurable" outcomes (L8, section 15.2)**
  are the parts of this architecture most likely to get quietly cut under
  deadline pressure, because they produce *fewer* findings, not more. Worth
  explicitly deciding upfront that a lower finding rate with real suppression
  is the intended behavior, not a bug to route around later.
- **This repo's `gate-hook.py` gap (docs/decisions.md item I)** and CLaiMB's
  L10 verification gate are conceptually the same kind of control (external,
  deterministic, blocks progression until a condition is independently
  satisfied). If we ever build `gate-hook.py` for real, it's worth designing
  it so the same mechanism could plausibly serve as L10's enforcement layer
  later, rather than building two unrelated gate mechanisms.

## 5. Bottom line

- **Fit:** strong on L1-L3 — we already have a working, hands-on Bronze/Silver/Gold(/Platinum)
  pipeline that matches CLaiMB's Data Foundation layer-for-layer. Reusable as-is
  conceptually; would need re-platforming from this demo's synthetic data to
  real customer-scoped ingestion, but the architecture pattern transfers directly.
- **Open risk:** L4-L11 (the 8-stage reasoning chain) is a large, mostly-unbuilt,
  cost-unknown system. The colleague's instinct to price it out first is
  correct — recommend a single vertical-slice pilot (one metric, all 11
  layers, real token/retry instrumentation) before committing to building all
  8 reasoning-layer skills, their registries, and the orchestrator.
