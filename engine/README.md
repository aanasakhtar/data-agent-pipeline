# engine/ — P0 foundational engine

Real software behind L4–L11, replacing prompt-only enforcement of schema
shape, verification independence, and state-machine gating. See
`MATURATION_PLAN.md` (F1) for why this exists and what it fixes.

## Scope — read this before extending anything here

This package implements exactly four things, and deliberately nothing more:

1. **`schemas.py`** — strict Pydantic v2 models for the 8 Platinum
   artifacts, checked against every real fixture currently in `artifacts/`.
2. **`verifier.py`** — the **deterministic third** of Layer 10: query
   re-execution, arithmetic cross-checks, provenance resolution. No LLM.
3. **`orchestrator.py`** — the state machine and the isolation payload
   builders that structurally prevent a layer from seeing fields it
   isn't supposed to.
4. **`run_pipeline.py`** — an end-to-end harness proving 1–3 against the
   real pilot fixtures and the real `dev.duckdb`.

**What this does NOT do:** call an LLM for any of L4/L5/L7/L8/L9/L11's
actual reasoning, or implement the adversarial-review half of L10
(semantic conformance, contradiction detection, narrative integrity —
see `verifier.py`'s module docstring for exactly where that boundary is
and why it's a separate, harder problem). Wiring an actual agent call
behind each `build_*_payload()` is the next piece of work, sequenced in
the maturation plan as P1.

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
# End-to-end harness against the real pilot fixtures + real DuckDB
python engine/run_pipeline.py

# Full test suite (28 tests: schema parsing, verifier PASS/REJECT/
# LOW_CONFIDENCE paths against real + deliberately corrupted data,
# orchestrator state machine + isolation enforcement)
pytest tests/ -v
```

Both were run against this exact repo state before being handed over —
`run_pipeline.py` exits 0, all 28 tests pass. `tests/conftest.py` will
`pytest.skip` the DB-dependent tests (not fail the whole suite) if you
run `pytest` before `dbt build --target local` has produced
`dev.duckdb`.

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
