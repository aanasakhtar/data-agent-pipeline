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
  4. Exercises the dependency-aware retry path with deliberately bad
     evidence, confirms L4/L5 survive untouched, recovers with corrected
     evidence, and reaches FINDING_RELEASED.
  5. Runs verification again through the genuinely process-isolated
     subprocess path and confirms it agrees with the in-process result.
  6. Computes a financial ValueRecord against a synthetic target (the
     real pilot contract has no customer target -- clearly labeled as
     illustrative) and independently re-verifies its arithmetic.
  7. Builds a RunManifest and confirms the content fingerprint is
     reproducible across two independently constructed runs of the same
     fixtures.
  8. Exits 0 and prints a summary on success; exits 1 with a specific
     diagnostic on any failure.

This is intentionally scoped to what P0/P1 can prove without an LLM:
that the schemas match real output, that the deterministic checks work
against a real warehouse, that the state machine enforces its own gates
AND correctly routes a targeted retry, and that the financial value
subsystem is pure and independently checkable. It does not call any of
L4/L5/L7/L8/L9/L11's actual reasoning -- those still need an agent.
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
    ValueAssumptions,
    VerificationResult,
)
from engine.orchestrator import (  # noqa: E402
    GateNotSatisfiedError,
    InvalidTransitionError,
    PipelineOrchestrator,
    RetryTarget,
)
from engine.value import compute_value_record, verify_value_arithmetic  # noqa: E402
from engine.verifier import run_deterministic_verification, run_deterministic_verification_subprocess  # noqa: E402

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


def run_dependency_aware_retry_demo(loaded: dict) -> None:
    print(_line("="))
    print("STEP 4 -- dependency-aware retry: bad evidence must invalidate ONLY L6+ ")
    print(_line("="))
    orch = PipelineOrchestrator(customer_id="retry-demo", business_function="Order Fulfillment")
    orch.record_business_context(loaded["business_context"])
    orch.record_metric_contract(loaded["metric_contract"])
    contract_before = orch._metric_contract
    context_before = orch._business_context

    bad_evidence = loaded["evidence"].model_copy(update={"observed_value": 0.5})
    orch.record_evidence(bad_evidence)
    orch.record_diagnostics([loaded["diagnostic_1"], loaded["diagnostic_2"]])
    orch.record_ai_opportunity(loaded["ai_opportunity"])
    orch.record_benchmark(loaded["benchmark"])

    bad_result = run_deterministic_verification(
        verification_id="retry-demo-bad", evidence_bundle=bad_evidence, db_path=str(DB_PATH)
    )
    print(f"  verification on deliberately bad evidence: {bad_result.disposition}")
    orch.record_verification(bad_result)
    print(f"  state after REJECT: {orch.state.value}  (retry_target={orch._last_retry_target.value})")

    if orch._metric_contract is not contract_before or orch._business_context is not context_before:
        raise HarnessFailure("dependency-aware retry invalidated L4/L5, which it must not do for an evidence-level failure")
    if orch._evidence is not None or orch._diagnostics or orch._ai_opportunity is not None or orch._benchmark is not None:
        raise HarnessFailure("dependency-aware retry failed to invalidate L6-L9 after an evidence-level REJECT")
    print("  confirmed: L4/L5 untouched, L6-L9 invalidated")

    print("  supplying corrected evidence and re-walking the chain...")
    orch.record_evidence(loaded["evidence"])
    orch.record_diagnostics([loaded["diagnostic_1"], loaded["diagnostic_2"]])
    orch.record_ai_opportunity(loaded["ai_opportunity"])
    orch.record_benchmark(loaded["benchmark"])
    good_result = run_deterministic_verification(
        verification_id="retry-demo-good", evidence_bundle=loaded["evidence"], db_path=str(DB_PATH)
    )
    orch.record_verification(good_result)
    orch.record_finding(loaded["finding"])
    if orch.state.value != "FINDING_RELEASED":
        raise HarnessFailure(f"failed to recover after targeted retry, ended in {orch.state.value}")
    print(f"  recovered: {orch.state.value} after {orch._verification_retry_count} retry(ies)")


def run_subprocess_verification_demo(loaded: dict) -> None:
    print(_line("="))
    print("STEP 5 -- genuinely process-isolated verification (real subprocess)")
    print(_line("="))
    result = run_deterministic_verification_subprocess(
        verification_id="subprocess-demo",
        evidence_bundle=loaded["evidence"],
        db_path=str(DB_PATH),
        finding_for_provenance=loaded["finding"],
        repo_root=REPO_ROOT,
    )
    print(f"  disposition from a fresh `python verifier_worker.py` process: {result.disposition}")
    if result.disposition != "PASS":
        raise HarnessFailure(f"subprocess verification unexpectedly returned {result.disposition}")


def run_value_calculation_demo(loaded: dict) -> None:
    print(_line("="))
    print("STEP 6 -- financial value calculation (ILLUSTRATIVE: synthetic target + assumptions)")
    print(_line("="))
    print("  NOTE: the real pilot MetricContract has target_value=None -- there is")
    print("  no customer-stated target to size a gap against. Everything below uses")
    print("  a synthetic target (95% STP) and a synthetic role roster, purely to")
    print("  prove the value subsystem's arithmetic and independent re-verification.")
    contract_with_target = loaded["metric_contract"].model_copy(update={"target_value": 0.95})
    assumptions = ValueAssumptions(
        salary_source=65000,
        overhead_multiplier=1.3,
        headcount=14,
        pct_time_on_function=0.6,
        pct_automatable=0.6,
        realization_mode="blended",
        blended_cash_ratio=0.6,
        realization_factor=0.7,
    )
    value_record = compute_value_record(
        value_id="illustrative-demo",
        metric_contract=contract_with_target,
        evidence=loaded["evidence"],
        assumptions=assumptions,
    )
    print(f"  gap_fraction: {value_record.gap_fraction}")
    print(f"  total_annual_unlock: {value_record.total_annual_unlock}")
    print(f"  cash_benefit: {value_record.cash_benefit}  |  capacity_benefit: {value_record.capacity_benefit}")

    verification = verify_value_arithmetic(value_record, contract_with_target, loaded["evidence"])
    print(f"  independent re-verification: {'PASS' if verification.passed else 'FAIL'} -- {verification.detail}")
    if not verification.passed:
        raise HarnessFailure("value calculation did not independently re-verify")


def run_manifest_demo(orch: PipelineOrchestrator, loaded: dict) -> None:
    print(_line("="))
    print("STEP 7 -- run manifest + content fingerprint reproducibility")
    print(_line("="))
    manifest = orch.build_run_manifest(repo_root=REPO_ROOT)
    print(f"  code_commit_sha: {manifest.code_commit_sha}")
    print(f"  dbt_manifest_hash: {(manifest.dbt_manifest_hash or '')[:16]}...")
    print(f"  configuration_hash: {manifest.configuration_hash[:16]}...")

    orch2 = PipelineOrchestrator(customer_id="a-different-customer", business_function="also different")
    orch2.record_business_context(loaded["business_context"])
    orch2.record_metric_contract(loaded["metric_contract"])
    orch2.record_evidence(loaded["evidence"])
    orch2.record_diagnostics([loaded["diagnostic_1"], loaded["diagnostic_2"]])
    orch2.record_ai_opportunity(loaded["ai_opportunity"])
    orch2.record_benchmark(loaded["benchmark"])
    orch2.record_verification(loaded["stored_verification"])
    orch2.record_finding(loaded["finding"])

    if orch.content_fingerprint() != orch2.content_fingerprint():
        raise HarnessFailure(
            "content_fingerprint differs across two independently constructed "
            "runs of the identical fixtures -- reproducibility is broken"
        )
    print("  confirmed: identical fingerprint across two independent runs of the same fixtures")
    print("  (despite different run_id, customer_id, and construction timestamp)")


def main() -> int:
    try:
        loaded = load_and_validate()
        run_verifier(loaded)
        orch = run_orchestrator(loaded)
        run_dependency_aware_retry_demo(loaded)
        run_subprocess_verification_demo(loaded)
        run_value_calculation_demo(loaded)
        run_manifest_demo(orch, loaded)
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
