# ClaimbAI — Base Pipeline Handoff

This is the base version referenced in the team handoff: a working,
locally-runnable proof of concept for the ClaimbAI data platform — a
medallion data pipeline (bronze/silver/gold/platinum) plus an 11-layer
evidence-driven reasoning chain (the CLaiMB architecture) that turns a
business goal into a verified, defensible finding about AI-adoption gaps.

**Start here, in order:** this file → `docs/architecture.md` →
`docs/local-testing.md` → run the quickstart below → read the maturity
scorecard in Part 2 before building on any specific layer.

---

## Part 1 — What's actually in this folder

| Path | What it is |
| --- | --- |
| `workflow.md` | The original gate-locked orchestrator-worker design spec this whole project is built from. |
| `CLaiMB_Data_Agent_Full_Multilayered_Architecture.md` | The 11-layer CLaiMB architecture spec (Bronze→Silver→Gold→Intent→KPI→Evidence→Diagnosis→AI-Opportunity→Benchmark→Verification→Synthesis). |
| `data-source/` | Synthetic "customer source system" — schema + generator (Faker-based, scale-parameterized) that stands in for a real customer's database. |
| `dbt/customer_platform/` | The medallion pipeline itself: dbt models for bronze/silver/gold/platinum, tests, a DuckDB local target (free) and a Snowflake target (real cloud path). |
| `.claude/skills/` | All 11 CLaiMB layers implemented as Claude Code skills, plus 2 operational skills (`new-customer-onboarding`, `weekly-report`). |
| `registry/` | Shared source-of-truth files the skills read from: `semantic_model.yml` (business terms → physical fields), `ontology_objects.yml` (relationship graph), `verified_queries/` (trusted, re-executable SQL), `metric_registry/` (KPI definitions). |
| `artifacts/` | Output of the one real pilot run so far — a full evidence chain for one metric, from business context through to a finished finding. Read these as worked examples of what each layer actually produces. |
| `.github/workflows/dbt_ci.yml` | CI gate: runs `dbt build` on every PR against an isolated Snowflake schema. |
| `dashboard/` | Streamlit app reading the platinum layer. |
| `docs/` | Everything else — setup runbooks, architecture mapping, competitive research, benchmarks, and the honest gap analysis this scorecard is drawn from. |

## Part 2 — Maturity scorecard (read this before extending anything)

Every claim below is backed by something that actually ran — see the
"Evidence" column. Nothing here is aspirational.

| Layer | What it does | Maturity | Evidence |
| --- | --- | --- | --- |
| L1 Bronze | Ingest & stage raw data | **Proven, benchmarked** | 72/72 dbt tests pass at demo scale; re-verified at 100x scale (770K rows, 11.28s transform time) — `docs/performance-benchmark.md` |
| L2 Silver | Conform, dedup, SCD2, quality-profile | **Proven** | Real dbt models + native SCD2 snapshot, tested | 
| L3 Gold | Canonical business entities, metric facts | **Proven**, honestly bounded | `dim_customers`/`fct_orders`/etc. built and tested; `gold_actor_activity`/`gold_text_profiles` explicitly reported `unavailable` rather than faked — see `artifacts/gold/manifest.json` |
| L4 Intent & Scope | Turn a stated goal into a bounded context | **Proven once** | One real `BusinessFunctionContext` built and used end-to-end; not yet tested against a second, differently-shaped goal |
| L5 KPI Resolution | Business goal → executable `MetricContract` | **Proven once, now backed by reusable infra** | One contract built, verified, and now resolvable through `registry/semantic_model.yml` + `registry/verified_queries/` instead of ad hoc SQL — `docs/architecture-upgrades.md` |
| L6 Evidence | Execute the contract, measure current state | **Proven, independently re-checked** | Query hash-verified; re-executed in a fresh DuckDB connection and matched exactly — `artifacts/verification/*.json` |
| L7 Diagnosis | Explain the measured gap | **Proven, demonstrated correct on both signal and noise** | Correctly labeled a plan-tier segment difference as noise (low confidence, `hypothesis`); correctly identified a real gap via process-variant analysis (40 orders / 4.13% completed with an unresolved ticket) — `docs/deep-research-ai-adoption-gaps.md` |
| L8 AI Opportunity | Score AI-suitability, allow refusal | **Proven the refusal path works; missing a dimension** | Correctly returned `NO_AI_RECOMMENDATION` on weak evidence instead of manufacturing a recommendation. **Known gap:** only scores task characteristics, not organizational/data readiness — flagged explicitly in `docs/deep-research-ai-adoption-gaps.md` Part 3 |
| L9 Benchmark | Qualify or suppress a comparison | **Proven the suppression path works** | Correctly suppressed a plan-tier cohort comparison for lack of comparability instead of presenting an unqualified target |
| L10 Verification | Independently falsify claims before release | **Core check proven; retry loop untested** | Re-execution + arithmetic + provenance checks all actually ran and passed. **Known gap:** the reject→retry loop described in the skill has never actually been exercised — no bad artifact has ever been deliberately run through it |
| L11 Synthesis | Assemble a finding from verified records only | **Proven once** | One real finding produced, numbers copied verbatim from verified upstream artifacts — `artifacts/findings/order-straight-through-rate-pilot-1.{json,md}` |

**One-line summary for the team:** this is a working, evidence-grounded
proof of concept where the *guardrails* (noise-vs-signal labeling,
honest refusal, benchmark suppression, independent re-verification) are
proven to actually fire correctly on real data — that's the hardest part
to get right and it's demonstrated, not just designed. What's *not* proven
yet: running more than one metric through the chain, running the 8
reasoning layers as separate agent turns with real cost/latency numbers,
and the verification retry loop under an actual failure.

## Part 3 — How good is this compared to what's already out there?

Full research: `docs/competitive-landscape.md` and
`docs/deep-research-ai-adoption-gaps.md`. Short version for planning
purposes:

- **Don't compete on NL-to-SQL / semantic layer** (L1-L6). Snowflake
  Cortex Analyst, Databricks Genie, and open-source Wren AI already do this
  at production scale with years of engineering behind them. We've borrowed
  their actual patterns (Cortex Analyst's Verified Query Repository, Wren
  AI's MDL semantic layer) rather than reinventing them from scratch — see
  `registry/semantic_model.yml` and `registry/verified_queries/`.
- **The real differentiation is L7-L11** — diagnose a gap, judge whether AI
  is actually the right fix (including refusing to recommend one), and
  adversarially verify the whole chain before a customer sees it. Nothing
  found in open source or from major vendors productizes this specific
  combination end-to-end. Palantir AIP is the closest philosophical cousin
  (governed ontology + action gates) but is a general platform, not
  specialized for this.
- **Object-centric process mining (Celonis's Process Intelligence Graph)**
  is the concrete next capability worth adding — our relationship graph
  (`registry/ontology_objects.yml`) is currently hand-declared, not mined
  from actual event sequences. `docs/deep-research-ai-adoption-gaps.md`
  Part 2 proves this matters: a process-variant analysis found a real gap
  (40 unresolved-ticket orders) that a flat rate metric completely missed.

## Part 4 — Quickstart (zero cost, no accounts needed)

```bash
# 1. Set up Python environment
python -m venv .venv
.venv/Scripts/pip install -r data-source/generator/requirements.txt
.venv/Scripts/pip install dbt-core dbt-duckdb

# 2. Generate synthetic data (already in dbt/customer_platform/seeds/ as raw_*.csv,
#    but this regenerates it / lets you change scale)
cd data-source/generator
../../.venv/Scripts/python generate_data.py --seed 42

# 3. Build the whole medallion pipeline locally
cd ../../dbt/customer_platform
../../.venv/Scripts/dbt deps
../../.venv/Scripts/dbt seed --target local
../../.venv/Scripts/dbt build --target local
# Expect: 72/72 PASS

# 4. Explore the result
../../.venv/Scripts/python -c "import duckdb; print(duckdb.connect('dev.duckdb').sql('select * from platinum.customer_360 limit 5'))"
```

Full setup for the real cloud path (Neon + Snowflake + Airbyte Cloud, all
free-tier) is in `docs/neon-setup.md`, `docs/snowflake-setup.md`,
`docs/airbyte-runbook.md`.

To see the reasoning chain (L4-L11) work end to end, read
`docs/claimb-pilot-run.md` alongside the `artifacts/` folder — it's the
worked example of every artifact type a skill produces.

## Part 5 — Recommended next steps for the team

In priority order (all detailed in `docs/deep-research-ai-adoption-gaps.md` Part 4):

1. Turn the process-variant discovery (Part 2 above) into a standing step
   in `.claude/skills/operational-diagnosis/SKILL.md` instead of a one-off query.
2. Add an organizational/data-readiness scoring dimension to L8
   (`AIOpportunityRecord`) — right now it only scores task fit.
3. Actually exercise the L10 reject→retry loop by deliberately breaking one
   artifact and confirming the loop catches and routes it correctly.
4. Instrument real per-layer token/cost numbers by running L4-L11 as
   separate agent turns instead of one continuous pass (the open question
   from `docs/claimb-idea-fit.md`, still unanswered).
5. Once (4) has a real number, revisit whether to build out the full
   registry infrastructure (`registry/advisory_catalog/`,
   `registry/framework_registry/` are currently empty placeholders) or
   keep leaning on external tools per Part 3 above.

## Part 6 — Known limitations (be upfront about these)

- Synthetic data only — no real customer has run through this.
- Only one metric (`order_straight_through_rate`) has ever been resolved
  end-to-end through all 11 layers.
- `gate-hook.py` (the hard-gate enforcement mechanism from `workflow.md`)
  was never built — PR review + required CI is the current stand-in.
- `registry/advisory_catalog/`, `registry/framework_registry/`,
  `registry/diagnostic_modules/`, `registry/benchmark_sources/` are
  documented placeholders, not populated registries.
- No multi-tenant/customer-isolation story exists yet — this is single-dataset.
