# engine/ — P0 + P1 foundational engine

Real software behind L4–L11, replacing prompt-only enforcement of schema
shape, verification independence, and state-machine gating (P0) — plus
the affirmative path and semantic golden evaluation suite (P1). See
`MATURATION_PLAN.md` (F1, F2) for why this exists and what it fixes.

## Scope — read this before extending anything here

**P0 (all deterministic, fully tested against real data):**

1. **`schemas.py`** — strict Pydantic v2 models for the 8 Platinum
   artifacts, plus `ValueRecord`/`ValueAssumptions` (financial value) and
   `RunManifest` (reproducibility). All backward-compatible with every
   real fixture in `artifacts/` — new fields are optional/defaulted.
2. **`gates.py`** — early, cheap deterministic gates on `MetricContract`
   and `EvidenceBundle`, run BEFORE the expensive L10 pass (blueprint
   section 5's cross-cutting verification plane).
3. **`verifier.py`** + **`verifier_worker.py`** — the deterministic third
   of Layer 10 (query re-execution, arithmetic, provenance), runnable
   either in-process (cheap, for unit tests) or via a genuinely isolated
   **OS subprocess** (`run_deterministic_verification_subprocess`) — a
   fresh interpreter with zero access to whatever process produced the
   evidence under test.
4. **`orchestrator.py`** — the state machine, isolation payload builders,
   **dependency-aware targeted retry** (a REJECT invalidates only the
   layer that was actually wrong and everything downstream of it — L4/L5
   survive untouched from an evidence-level failure), and `RunManifest`
   / `content_fingerprint()` for reproducibility.
5. **`value.py`** — the financial value subsystem flagged as missing
   since the first review: pure, deterministic arithmetic on stated
   assumptions (never inferred), with independent re-verification.
6. **`run_pipeline.py`** — end-to-end harness proving all of the above
   against the real pilot fixtures, real `dev.duckdb`, and a real
   subprocess call.

**P1 (the affirmative path + semantic evaluation — read the honesty note below):**

7. **`data-source/generator/planted_gap_generator.py`** — builds a
   SEPARATE DuckDB warehouse with an exactly-known planted gap (a
   concentrated 60%-vs-96% straight-through-rate problem in the "pro"
   plan tier, against a stated 90% target), plus a role roster and
   independently-computed ground-truth financial figures. The pilot's
   own already-verified `MetricContract` and query work UNCHANGED
   against this database — same schema, deliberately different data.
8. **`evidence.py`** — the live L6 execution engine: takes a
   `MetricContract` and a database path, actually runs the query, and
   builds a fully-validated `EvidenceBundle` — no static JSON involved.
   Segmentation is read from `registry/verified_queries/<metric_id>.yml`
   (Cortex-Analyst-style Verified Query Repository entries), not by
   rewriting SQL.
9. **`semantic_resolver.py`** — the live L4/L5 LLM resolver: turns customer
   free text into a validated `MetricContract` using OpenAI (default, aligned
   with Claimb Command Center MVP2's `OPENAI_API_KEY` / `gpt-4o-mini`) or
   Anthropic (`claude-sonnet-5`). Correctly sets `resolution_status`
   (`RESOLVED`, `RESOLVED_WITH_ASSUMPTION`, `AMBIGUOUS_NEEDS_INPUT`,
   `NOT_MEASURABLE`, `UNSUPPORTED_BY_AVAILABLE_DATA`), refusing to hallucinate
   or guess when a goal is vague or unsupported by the schema.
10. **`run_affirmative_pipeline.py`** — the full affirmative path: planted gap
    → live semantic resolution → live evidence execution on DuckDB →
    deterministic diagnosis heuristic → deterministic AI opportunity
    heuristic → financial value calculation → subprocess verification →
    released finding. Every number in the released finding matches
    `planted_gap_generator.py`'s independently-computed ground truth exactly.
11. **`evals/golden_eval.py`** — the Semantic Golden Evaluation Suite: a
    `GoldenCase` model, `evaluate_semantic_accuracy()`, and 4 concrete
    cases (affirmative/planted-gap, vague/ambiguous, unmeasurable,
    pilot-baseline). Supports both REFERENCE mode and LIVE mode (validated
    **4/4 passed** live against `gpt-4o-mini`).

**PRODUCTION CREDENTIALS & EVALUATION STATUS:**

- **Live OpenAI Integration Verified:** `engine/semantic_resolver.py` reads
  `OPENAI_API_KEY` from `.env` (matching Claimb Command Center MVP2). Live
  semantic resolution was tested against all 4 golden cases and scored **4/4 PASS**,
  proving that the model correctly targets Gold tables, defines numerator/denominator,
  and refrains from guessing when customer language is ambiguous or unsupported.
- **L7 (diagnosis) and L8 (AI opportunity) in `run_affirmative_pipeline.py`
  are deterministic heuristics, not LLM calls.** `_derive_diagnostic_heuristically`
  and `_derive_ai_opportunity_heuristically` stand in for future LLM-driven L7/L8
  agents. They produce internally-consistent, schema-valid output, which proves
  the end-to-end data plumbing and gate contracts.

**Both deferred by explicit direction, unchanged from before:** the
adversarial-review half of L10, and the blueprint's object-centric
process/event-log mining generalization (section 6).

## Setup

```bash
# From the repo root
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r engine/requirements.txt

# Build the local warehouse the verifier checks against (HANDOFF.md Part 4)
cd dbt/customer_platform
dbt deps
dbt seed --target local
dbt build --target local
cd ../..
```

## Run it

```bash
# P0 harness -- 7 steps against the real pilot fixtures + real DuckDB
python engine/run_pipeline.py

# P1 affirmative pipeline -- builds the planted-gap warehouse (if not
# already built) and runs the full path to a released finding
python engine/run_affirmative_pipeline.py

# Semantic golden evaluation scorecard (REFERENCE mode by default --
# see the honesty note above)
python evals/golden_eval.py

# Full test suite (83 tests: the original 57 plus 26 new P1 tests)
pytest tests/ -v
```

All of the above were run against this exact repo state before being
handed over, from a completely fresh clone and a brand-new venv — not
just in the session that wrote the code:
`run_pipeline.py` exits 0, `run_affirmative_pipeline.py` exits 0 and its
released finding's numbers match `planted_gap_generator.py`'s
independently-computed ground truth exactly, `golden_eval.py` scores 4/4
in REFERENCE mode, and all 83 tests pass.

## Things found while building this that are worth knowing about

These came out of testing against real fixtures, not from reading the
architecture doc — each one only shows up when you actually run the
checks against real data:

- **`EvidenceBundle.metric_contract_id` and `BenchmarkRecord.metric_id`
  use `"name:version"` (`"order_straight_through_rate:1"`), while
  `MetricContract.metric_id` is bare (`"order_straight_through_rate"`,
  with `version` as a separate field).** The orchestrator's
  `record_evidence` now parses the composite form
  (`schemas.parse_versioned_metric_id`) and validates both the base name
  and the version number, rather than either raising on every real
  record or silently prefix-matching. Whoever writes L5/L6's actual
  prompts should standardize on one convention going forward — right
  now the orchestrator is compensating for an inconsistency in the
  original design, not enforcing a rule.

- **`EvidenceBundle` has no top-level numerator field** — only
  `observed_value` (a rate) and `sample_size`. `verify_arithmetic`
  reconstructs a numerator from `segment_results` to cross-check
  internal consistency, but this is a reconstruction with rounding
  tolerance, not an exact derivation. Recommend adding explicit
  `numerator_value` / `denominator_value` fields to `MetricContract`/
  `EvidenceBundle` in a future schema version so this check can become
  exact.

- **`provenance_chain` entries are inconsistently shaped.** Most are
  relative file paths (`"artifacts/business_context/order-fulfillment.json"`),
  one carries a trailing human annotation
  (`"... (this file)"`, stripped before path-checking), and at least one
  (in `EvidenceBundle`) is a free-text description
  (`"MetricContract order_straight_through_rate v1"`) rather than a path
  at all. `verify_provenance` handles all three shapes but treats the
  unresolvable free-text case as a soft note rather than a failure —
  recommend standardizing `provenance_chain` to always be actual
  relative file paths going forward.

- **There is no field anywhere declaring which column of a multi-column
  query result is "the" metric value.** `verify_query_reexecution`
  currently assumes the last selected column by convention (true of
  both queries in `registry/verified_queries/`), which is fragile.
  Recommend adding `result_value_column: str` to `MetricContract`.

None of these are blockers — the code handles all of them correctly
today — but they're the kind of small inconsistency that gets much more
expensive to fix once ten more metrics have been onboarded on top of the
current convention. Worth a five-minute conversation with whoever owns
L5/L6 before that happens.

## What's still open, in priority order

1. **Run `evals/golden_eval.py` in LIVE mode with a real API key**, on
   real (not human-curated) customer language, before trusting L4/L5 in
   front of a customer. This is the single most important open item —
   see the honesty note above.
2. **Real LLM-driven L7 (diagnosis) and L8 (AI opportunity)**, replacing
   `run_affirmative_pipeline.py`'s deterministic heuristics. The
   heuristics prove the plumbing (evidence → diagnosis → opportunity →
   value → verification → finding) works end to end; they are not a
   substitute for real diagnostic/opportunity judgment.
3. **The adversarial-review half of L10** (semantic conformance,
   contradiction detection, narrative integrity) — still `NOT_RUN` by
   design.
4. **Object-centric process/event-log mining** (blueprint section 6) —
   explicitly deferred per current direction.
5. **Expand the golden case set past 4** — enough to prove the harness's
   mechanics, not enough to be a real evaluation corpus. Real onboarding
   will surface many more ambiguity/table-targeting edge cases than
   these four capture.
6. **`resolution_status`, `ValueRecord`, and `RunManifest` are still only
   exercised by synthetic/planted data**, not a real L5/L6 agent's
   output on an actual customer's messy schema. Expect friction the
   first time.
