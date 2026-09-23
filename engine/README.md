# engine/ — P0 foundational engine

Real software behind L4–L11, replacing prompt-only enforcement of schema
shape, verification independence, and state-machine gating. See
`MATURATION_PLAN.md` (F1) for why this exists and what it fixes.

## Scope — read this before extending anything here

This package now implements, all tested against real repo data and a
real DuckDB warehouse:

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

**What this does NOT do, on purpose:** anything from the blueprint's
object-centric process/event-log mining generalization (section 6) —
deliberately deferred while this stays focused on the metrics chain. It
also still doesn't call an LLM for L4/L5/L7/L8/L9/L11's actual reasoning,
or implement the adversarial-review half of L10 (semantic conformance,
contradiction detection, narrative integrity).

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
# End-to-end harness -- 7 steps: schema validation, in-process
# verification, full orchestrator walk, dependency-aware retry recovery,
# subprocess-isolated verification, an illustrative value calculation,
# and run-manifest reproducibility.
python engine/run_pipeline.py

# Full test suite (57 tests)
pytest tests/ -v
```

Both were run against this exact repo state before being handed over --
`run_pipeline.py` exits 0, all 57 tests pass, confirmed from a completely
fresh clone and a brand-new venv (not just in the session that wrote the
code).

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

## What's still open (from the maturation blueprint), in priority order

1. **The adversarial-review half of L10** (semantic conformance,
   contradiction detection, narrative integrity) — still `NOT_RUN` by
   design. This needs an actual model call given a fresh context
   containing only the record under test, per `verifier.py`'s module
   docstring. Wiring this is what turns `PASS` here into a true 7-engine
   `PASS`, not a 3-engine one.
2. **No LLM calls anywhere.** `build_*_payload()` on the orchestrator
   produces exactly the narrow, isolated input each layer should
   receive — nothing yet calls a model with it. That's P1: prove the
   affirmative reasoning path on a planted-gap dataset with a known
   expected finding and dollar value.
3. **Object-centric process/event-log mining** (blueprint section 6) —
   explicitly deferred per current direction; this package stays
   metrics-focused.
4. **`resolution_status` and the `ValueRecord`/`RunManifest` schemas are
   new and unpopulated by any real fixture** — they're designed and
   tested against synthetic cases, not yet exercised by an actual L5/L6
   agent output. Expect some friction the first time a real one is
   produced; treat this package's tests as the contract that output
   needs to satisfy, not as proof the contract is exactly right yet.
