#!/usr/bin/env python3
"""
engine/run_pipeline.py
========================
Runnable end-to-end harness. From the repo root, after `dbt build --target
local` has produced dbt/customer_platform/dev.duckdb (see HANDOFF.md
Part 4 quickstart):

    python engine/run_pipeline.py

What it does, in order:

  1. Loads every real fixture in artifacts/ for the pilot metric and
     validates each against its Pydantic schema. A validation failure on
     any one file is reported and does not crash the run of the others
     -- you get a full report, not a stop-at-first-error.
  2. Re-runs the deterministic verifier (query re-execution, arithmetic,
     provenance) FRESH against dev.duckdb -- independent of, and without
     reading, the disposition already stored in
     artifacts/verification/order_straight_through_rate_v1_verify.json --
     and compares its own disposition against that stored one.
  3. Drives the whole thing through PipelineOrchestrator in order,
     confirming every state transition is legal and the finding is only
     released after a passing verification gate.
  4. Exits 0 and prints a summary on success; exits 1 with a specific
     diagnostic on any failure.

This is intentionally scoped to what P0 can prove without an LLM: that
the schemas match real output, that the deterministic checks work
against a real warehouse, and that the state machine enforces its own
gates. It does not call any of L4/L5/L7/L8/L9/L11's actual reasoning --
those still need an agent, and proving THEM is P1's planted-gap dataset,
not this harness.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from engine.schemas import (  # noqa: E402
    AIOpportunityRecord,
    BenchmarkRecord,
    BusinessFunctionContext,
    DiagnosticRecord,
    EvidenceBundle,
    FindingDraft,
    MetricContract,
    VerificationResult,
)
from engine.orchestrator import (  # noqa: E402
    GateNotSatisfiedError,
    InvalidTransitionError,
    PipelineOrchestrator,
)
from engine.verifier import run_deterministic_verification  # noqa: E402

DB_PATH = REPO_ROOT / "dbt" / "customer_platform" / "dev.duckdb"

FIXTURES = {
    "business_context": (REPO_ROOT / "artifacts/business_context/order-fulfillment.json", BusinessFunctionContext),
    "metric_contract": (REPO_ROOT / "artifacts/metric_contracts/order_straight_through_rate.json", MetricContract),
    "evidence": (REPO_ROOT / "artifacts/evidence/order_straight_through_rate_20260918T161600Z.json", EvidenceBundle),
    "diagnostic_1": (REPO_ROOT / "artifacts/diagnostics/exception_concentration_plan_tier.json", DiagnosticRecord),
    "diagnostic_2": (REPO_ROOT / "artifacts/diagnostics/process_variant_analysis.json", DiagnosticRecord),
    "ai_opportunity": (REPO_ROOT / "artifacts/ai_opportunities/order-fulfillment-ai-assessment.json", AIOpportunityRecord),
    "benchmark": (REPO_ROOT / "artifacts/benchmarks/plan_tier_pro_cohort.json", BenchmarkRecord),
    "stored_verification": (REPO_ROOT / "artifacts/verification/order_straight_through_rate_v1_verify.json", VerificationResult),
    "finding": (REPO_ROOT / "artifacts/findings/order-straight-through-rate-pilot-1.json", FindingDraft),
}


class HarnessFailure(Exception):
    pass


def _line(char: str = "-") -> str:
    return char * 78


def load_and_validate() -> dict:
    print(_line("="))
    print("STEP 1 -- schema validation against real fixtures")
    print(_line("="))
    loaded = {}
    failures = []
    for name, (path, model) in FIXTURES.items():
        try:
            data = json.loads(path.read_text())
            obj = model.model_validate(data)
            loaded[name] = obj
            print(f"  OK    {name:<20} {path.relative_to(REPO_ROOT)}")
        except Exception as exc:  # noqa: BLE001 -- report every failure, don't stop at first
            failures.append((name, path, exc))
            print(f"  FAIL  {name:<20} {path.relative_to(REPO_ROOT)}")
            print(f"        {exc}")
    print()
    if failures:
        raise HarnessFailure(f"{len(failures)} fixture(s) failed schema validation: {[f[0] for f in failures]}")
    return loaded


def run_verifier(loaded: dict) -> None:
    print(_line("="))
    print("STEP 2 -- deterministic re-verification against a FRESH read-only DuckDB connection")
    print(_line("="))
    if not DB_PATH.exists():
        raise HarnessFailure(
            f"database not found at {DB_PATH}. Run `dbt build --target local` "
            "from dbt/customer_platform/ first (see HANDOFF.md Part 4)."
        )

    evidence: EvidenceBundle = loaded["evidence"]
    finding: FindingDraft = loaded["finding"]
    stored_verification: VerificationResult = loaded["stored_verification"]

    fresh = run_deterministic_verification(
        verification_id="run_pipeline_harness_reverification",
        evidence_bundle=evidence,
        db_path=str(DB_PATH),
        finding_for_provenance=finding,
        repo_root=REPO_ROOT,
    )

    print(f"  stored disposition (from artifacts/verification/*.json): {stored_verification.disposition}")
    print(f"  fresh disposition  (recomputed by this harness, just now): {fresh.disposition}")
    print()
    print("  fresh engine results:")
    for engine_name, result in fresh.engine_results.model_dump().items():
        print(f"    {engine_name:<20} {result}")
    print()

    if fresh.disposition not in ("PASS", "LOW_CONFIDENCE"):
        raise HarnessFailure(
            f"fresh deterministic re-verification produced disposition="
            f"{fresh.disposition!r} -- the stored artifact's numbers do not "
            "independently reproduce against the current warehouse"
        )

    if stored_verification.disposition == "PASS" and fresh.disposition != "PASS":
        # Not necessarily a bug -- the stored result also ran semantic/
        # benchmark/contradiction checks this harness doesn't -- but worth
        # surfacing loudly rather than silently accepting a downgrade.
        print(
            "  NOTE: stored verification was PASS on the full 7-engine "
            "contract; this harness's deterministic-only subset landed on "
            f"{fresh.disposition}. This is expected (this harness runs 3 of "
            "7 engines) and is not itself a failure."
        )


def run_orchestrator(loaded: dict) -> PipelineOrchestrator:
    print(_line("="))
    print("STEP 3 -- drive the full state machine with real fixtures")
    print(_line("="))
    orch = PipelineOrchestrator(
        customer_id="pilot-customer-1",
        business_function=loaded["business_context"].business_function,
    )
    print(f"  run_id: {orch.run_id}")

    steps = [
        ("record_business_context", loaded["business_context"]),
        ("record_metric_contract", loaded["metric_contract"]),
        ("record_evidence", loaded["evidence"]),
        ("record_diagnostics", [loaded["diagnostic_1"], loaded["diagnostic_2"]]),
        ("record_ai_opportunity", loaded["ai_opportunity"]),
        ("record_benchmark", loaded["benchmark"]),
        ("record_verification", loaded["stored_verification"]),
        ("record_finding", loaded["finding"]),
    ]
    for method_name, arg in steps:
        getattr(orch, method_name)(arg)
        print(f"  {method_name:<24} -> {orch.state.value}")

    if orch.state.value != "FINDING_RELEASED":
        raise HarnessFailure(f"expected final state FINDING_RELEASED, got {orch.state.value}")

    print()
    print("  isolation check: Synthesis payload must not carry query/source_objects")
    orch_probe = PipelineOrchestrator(customer_id="probe", business_function="probe")
    orch_probe.record_business_context(loaded["business_context"])
    orch_probe.record_metric_contract(loaded["metric_contract"])
    orch_probe.record_evidence(loaded["evidence"])
    orch_probe.record_diagnostics([loaded["diagnostic_1"], loaded["diagnostic_2"]])
    orch_probe.record_ai_opportunity(loaded["ai_opportunity"])
    orch_probe.record_benchmark(loaded["benchmark"])
    orch_probe.record_verification(loaded["stored_verification"])
    payload = orch_probe.build_synthesis_payload()
    for forbidden in ("query", "query_hash", "source_objects"):
        if hasattr(payload, forbidden):
            raise HarnessFailure(f"SynthesisLayerPayload unexpectedly exposes {forbidden!r}")
    print(f"    confirmed absent: query, query_hash, source_objects")
    print(f"    payload fields present: {list(payload.__dataclass_fields__.keys())}")

    return orch


def main() -> int:
    try:
        loaded = load_and_validate()
        run_verifier(loaded)
        orch = run_orchestrator(loaded)
    except HarnessFailure as exc:
        print(_line("="))
        print(f"HARNESS FAILED: {exc}")
        print(_line("="))
        return 1

    print(_line("="))
    print("ALL CHECKS PASSED")
    print(_line("="))
    print(json.dumps(orch.summary(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
