from __future__ import annotations

import pytest

from engine.orchestrator import (
    GateNotSatisfiedError,
    InvalidTransitionError,
    PipelineOrchestrator,
    PipelineState,
)
from engine.schemas import VerificationResult


def _build_full_run(
    business_context, metric_contract, evidence, diagnostic_exception_concentration,
    diagnostic_process_variant, ai_opportunity, benchmark,
) -> PipelineOrchestrator:
    orch = PipelineOrchestrator(customer_id="pilot-customer-1", business_function="Order Fulfillment")
    orch.record_business_context(business_context)
    orch.record_metric_contract(metric_contract)
    orch.record_evidence(evidence)
    orch.record_diagnostics([diagnostic_exception_concentration, diagnostic_process_variant])
    orch.record_ai_opportunity(ai_opportunity)
    orch.record_benchmark(benchmark)
    return orch


def test_full_pipeline_reaches_finding_released(
    business_context, metric_contract, evidence, diagnostic_exception_concentration,
    diagnostic_process_variant, ai_opportunity, benchmark, stored_verification, finding,
):
    orch = _build_full_run(
        business_context, metric_contract, evidence, diagnostic_exception_concentration,
        diagnostic_process_variant, ai_opportunity, benchmark,
    )
    orch.record_verification(stored_verification)
    orch.record_finding(finding)
    assert orch.state == PipelineState.FINDING_RELEASED
    # 9 transitions: CREATED->INTENT_RESOLVED->METRICS_RESOLVED->
    # CURRENT_STATE_MEASURED->OPERATIONALLY_DIAGNOSED->
    # AI_OPPORTUNITIES_ASSESSED->BENCHMARKED->VERIFICATION->
    # SYNTHESIZED->FINDING_RELEASED
    assert len(orch.transition_log) == 9


def test_evidence_metric_id_cross_check_accepts_versioned_reference(
    business_context, metric_contract, evidence,
):
    """evidence.metric_contract_id is 'order_straight_through_rate:1',
    metric_contract.metric_id is bare 'order_straight_through_rate' with
    version=1 -- this must reconcile, not raise."""
    orch = PipelineOrchestrator(customer_id="x", business_function="y")
    orch.record_business_context(business_context)
    orch.record_metric_contract(metric_contract)
    orch.record_evidence(evidence)  # must not raise
    assert orch.state == PipelineState.CURRENT_STATE_MEASURED


def test_evidence_version_mismatch_is_rejected(business_context, metric_contract, evidence):
    bad_evidence = evidence.model_copy(update={"metric_contract_id": "order_straight_through_rate:99"})
    orch = PipelineOrchestrator(customer_id="x", business_function="y")
    orch.record_business_context(business_context)
    orch.record_metric_contract(metric_contract)
    with pytest.raises(GateNotSatisfiedError, match="version"):
        orch.record_evidence(bad_evidence)


def test_out_of_order_recording_is_refused(evidence):
    orch = PipelineOrchestrator(customer_id="x", business_function="y")
    with pytest.raises(GateNotSatisfiedError):
        orch.record_evidence(evidence)


def test_ambiguous_metric_contract_is_refused_and_state_does_not_advance(business_context, metric_contract):
    from engine.orchestrator import MetricNotResolvableError

    bad = metric_contract.model_copy(update={"resolution_status": "AMBIGUOUS_NEEDS_INPUT"})
    orch = PipelineOrchestrator(customer_id="x", business_function="y")
    orch.record_business_context(business_context)
    with pytest.raises(MetricNotResolvableError):
        orch.record_metric_contract(bad)
    assert orch.state == PipelineState.INTENT_RESOLVED
    assert orch._metric_contract is None
    # A corrected contract must still work from the same state afterward.
    orch.record_metric_contract(metric_contract)
    assert orch.state == PipelineState.METRICS_RESOLVED


def test_unusable_evidence_is_refused_and_state_does_not_advance(business_context, metric_contract, evidence):
    from engine.orchestrator import EvidenceNotUsableError

    bad = evidence.model_copy(update={"data_quality_status": "UNUSABLE"})
    orch = PipelineOrchestrator(customer_id="x", business_function="y")
    orch.record_business_context(business_context)
    orch.record_metric_contract(metric_contract)
    with pytest.raises(EvidenceNotUsableError):
        orch.record_evidence(bad)
    assert orch.state == PipelineState.METRICS_RESOLVED
    assert orch._evidence is None


def test_illegal_direct_transition_is_refused():
    orch = PipelineOrchestrator(customer_id="x", business_function="y")
    with pytest.raises(InvalidTransitionError):
        orch.transition(PipelineState.FINDING_RELEASED)


def test_synthesis_payload_excludes_source_data(
    business_context, metric_contract, evidence, diagnostic_exception_concentration,
    diagnostic_process_variant, ai_opportunity, benchmark, stored_verification,
):
    """The structural enforcement this whole module exists for: L11 must
    not be able to see the raw SQL or warehouse object names."""
    orch = _build_full_run(
        business_context, metric_contract, evidence, diagnostic_exception_concentration,
        diagnostic_process_variant, ai_opportunity, benchmark,
    )
    orch.record_verification(stored_verification)
    payload = orch.build_synthesis_payload()
    for forbidden_field in ("query", "query_hash", "source_objects"):
        assert not hasattr(payload, forbidden_field), f"payload leaks {forbidden_field}"
    assert payload.verified_metric_value == pytest.approx(0.9047, abs=1e-4)


def test_evidence_layer_payload_excludes_business_context(metric_contract, business_context, evidence):
    """L6 (evidence measurement) must not see BusinessFunctionContext or
    any financial data -- only the metric contract."""
    orch = PipelineOrchestrator(customer_id="x", business_function="y")
    orch.record_business_context(business_context)
    orch.record_metric_contract(metric_contract)
    payload = orch.build_evidence_payload()
    assert not hasattr(payload, "business_function")
    assert not hasattr(payload, "customer_goal")
    assert payload.metric_contract.metric_id == metric_contract.metric_id


def test_reject_disposition_triggers_retry_then_human_review(
    business_context, metric_contract, evidence, diagnostic_exception_concentration,
    diagnostic_process_variant, ai_opportunity, benchmark, stored_verification, finding,
):
    """
    Updated for dependency-aware retry: a REJECT no longer parks the
    pipeline at a static TARGETED_RETRY state -- it routes THROUGH
    TARGETED_RETRY straight to whichever earlier state the invalidated
    layer requires regenerating from (see classify_retry_target). This
    test forces an unclassifiable REJECT (all engine strings say PASS,
    which cannot happen from a real verifier but exercises the
    conservative fallback), which routes to METRICS_RESOLVED -- the
    caller must then re-supply evidence/diagnostics/ai_opportunity/
    benchmark before verification can run again, exactly as a real
    caller responding to a targeted retry would have to.
    """
    orch = _build_full_run(
        business_context, metric_contract, evidence, diagnostic_exception_concentration,
        diagnostic_process_variant, ai_opportunity, benchmark,
    )

    def forced_reject(vid: str) -> VerificationResult:
        return VerificationResult(
            verification_id=vid,
            checked_records=["x"],
            engine_results=stored_verification.engine_results,  # all PASS strings -- unclassifiable
            disposition="REJECT",
            retry_count=0,
            notes="forced for test",
        )

    def resupply_to_benchmarked():
        orch.record_evidence(evidence)
        orch.record_diagnostics([diagnostic_exception_concentration, diagnostic_process_variant])
        orch.record_ai_opportunity(ai_opportunity)
        orch.record_benchmark(benchmark)

    orch.record_verification(forced_reject("r1"))
    assert orch.state == PipelineState.METRICS_RESOLVED  # routed via conservative RETRY_EVIDENCE default
    assert orch._verification_retry_count == 1

    resupply_to_benchmarked()
    orch.record_verification(forced_reject("r2"))
    assert orch.state == PipelineState.METRICS_RESOLVED
    assert orch._verification_retry_count == 2

    resupply_to_benchmarked()
    orch.record_verification(forced_reject("r3"))  # exceeds MAX_VERIFICATION_RETRIES (2)
    assert orch.state == PipelineState.HUMAN_REVIEW
    assert orch._verification_retry_count == 3

    with pytest.raises(GateNotSatisfiedError):
        orch.record_finding(finding)


def test_pass_disposition_allows_synthesis_directly(
    business_context, metric_contract, evidence, diagnostic_exception_concentration,
    diagnostic_process_variant, ai_opportunity, benchmark, stored_verification, finding,
):
    orch = _build_full_run(
        business_context, metric_contract, evidence, diagnostic_exception_concentration,
        diagnostic_process_variant, ai_opportunity, benchmark,
    )
    orch.record_verification(stored_verification)
    assert orch.state == PipelineState.VERIFICATION
    orch.record_finding(finding)
    assert orch.state == PipelineState.FINDING_RELEASED


# ---------------------------------------------------------------------------
# Dependency-aware retry (blueprint section 17)
# ---------------------------------------------------------------------------


def test_evidence_level_reject_invalidates_only_l6_and_below(
    business_context, metric_contract, evidence, diagnostic_exception_concentration,
    diagnostic_process_variant, ai_opportunity, benchmark, db_path,
):
    from engine.orchestrator import RetryTarget
    from engine.verifier import run_deterministic_verification

    orch = _build_full_run(
        business_context, metric_contract, evidence, diagnostic_exception_concentration,
        diagnostic_process_variant, ai_opportunity, benchmark,
    )
    contract_before = orch._metric_contract
    context_before = orch._business_context

    bad_evidence = evidence.model_copy(update={"observed_value": 0.5})
    bad_result = run_deterministic_verification(
        verification_id="dep-retry", evidence_bundle=bad_evidence, db_path=db_path
    )
    assert bad_result.disposition == "REJECT"

    # Note: the orchestrator's own evidence was the GOOD one recorded via
    # _build_full_run; we're feeding it a verification result computed
    # against a hypothetically-bad bundle to exercise classification and
    # invalidation in isolation from re-deriving evidence ourselves.
    orch.record_verification(bad_result)

    assert orch.state == PipelineState.METRICS_RESOLVED
    assert orch._last_retry_target == RetryTarget.RETRY_EVIDENCE
    # L4/L5 survive untouched -- same object identity, not just equal value
    assert orch._metric_contract is contract_before
    assert orch._business_context is context_before
    # L6 and everything downstream is cleared
    assert orch._evidence is None
    assert orch._diagnostics == ()
    assert orch._ai_opportunity is None
    assert orch._benchmark is None


def test_recovery_after_dependency_aware_retry_reaches_finding_released(
    business_context, metric_contract, evidence, diagnostic_exception_concentration,
    diagnostic_process_variant, ai_opportunity, benchmark, finding, db_path,
):
    from engine.verifier import run_deterministic_verification

    orch = _build_full_run(
        business_context, metric_contract, evidence, diagnostic_exception_concentration,
        diagnostic_process_variant, ai_opportunity, benchmark,
    )
    bad_evidence = evidence.model_copy(update={"observed_value": 0.5})
    bad_result = run_deterministic_verification(verification_id="r1", evidence_bundle=bad_evidence, db_path=db_path)
    orch.record_verification(bad_result)
    assert orch.state == PipelineState.METRICS_RESOLVED

    # Supply corrected evidence and walk the rest of the chain again --
    # this is what a real orchestrating caller (or future agent-calling
    # code) would do in response to a targeted retry.
    orch.record_evidence(evidence)
    orch.record_diagnostics([diagnostic_exception_concentration, diagnostic_process_variant])
    orch.record_ai_opportunity(ai_opportunity)
    orch.record_benchmark(benchmark)
    good_result = run_deterministic_verification(
        verification_id="r2", evidence_bundle=evidence, db_path=db_path
    )
    assert good_result.disposition == "PASS"
    orch.record_verification(good_result)
    orch.record_finding(finding)

    assert orch.state == PipelineState.FINDING_RELEASED
    assert orch._verification_retry_count == 1


def test_verification_only_retry_target_invalidates_nothing_upstream(
    business_context, metric_contract, evidence, diagnostic_exception_concentration,
    diagnostic_process_variant, ai_opportunity, benchmark, stored_verification,
):
    """RETRY_VERIFICATION_ONLY (e.g. a synthesis-level narrative_integrity
    failure) should not force L6-L9 to be regenerated."""
    from engine.orchestrator import RetryTarget

    orch = _build_full_run(
        business_context, metric_contract, evidence, diagnostic_exception_concentration,
        diagnostic_process_variant, ai_opportunity, benchmark,
    )
    evidence_before = orch is not None and evidence  # keep reference for clarity
    reject_narrative_only = VerificationResult(
        verification_id="narrative-only",
        checked_records=["x"],
        engine_results=stored_verification.engine_results.model_copy(
            update={"narrative_integrity": "FAIL -- headline overstates the verified figure"}
        ),
        disposition="REJECT",
        retry_count=0,
        notes="forced for test",
    )
    orch.record_verification(reject_narrative_only)
    assert orch.state == PipelineState.BENCHMARKED
    assert orch._last_retry_target == RetryTarget.RETRY_VERIFICATION_ONLY
    assert orch._evidence is evidence_before
    assert orch._ai_opportunity is ai_opportunity
    assert orch._benchmark is benchmark


# ---------------------------------------------------------------------------
# Run manifest and content fingerprint (blueprint section 14)
# ---------------------------------------------------------------------------


def test_content_fingerprint_identical_across_independent_runs_of_same_fixtures(
    business_context, metric_contract, evidence, diagnostic_exception_concentration,
    diagnostic_process_variant, ai_opportunity, benchmark, stored_verification, finding,
):
    def build(customer_id):
        o = PipelineOrchestrator(customer_id=customer_id, business_function="Order Fulfillment")
        o.record_business_context(business_context)
        o.record_metric_contract(metric_contract)
        o.record_evidence(evidence)
        o.record_diagnostics([diagnostic_exception_concentration, diagnostic_process_variant])
        o.record_ai_opportunity(ai_opportunity)
        o.record_benchmark(benchmark)
        o.record_verification(stored_verification)
        o.record_finding(finding)
        return o

    orch_a = build("customer-A")
    orch_b = build("customer-B")
    assert orch_a.run_id != orch_b.run_id
    assert orch_a.content_fingerprint() == orch_b.content_fingerprint()


def test_run_manifest_captures_best_effort_provenance(
    business_context, metric_contract, evidence, repo_root,
):
    orch = PipelineOrchestrator(customer_id="x", business_function="y")
    orch.record_business_context(business_context)
    orch.record_metric_contract(metric_contract)
    orch.record_evidence(evidence)
    manifest = orch.build_run_manifest(repo_root=repo_root, model_provider="anthropic", model_version="claude-sonnet-5")
    assert manifest.run_id == orch.run_id
    assert manifest.status == "CURRENT_STATE_MEASURED"
    assert manifest.configuration_hash == orch.content_fingerprint()
    # code_commit_sha/dbt_manifest_hash are best-effort -- in THIS repo
    # (a real git checkout with a built dbt target) both should resolve,
    # but the important contract is that they're None rather than
    # fabricated when they can't.
    assert manifest.code_commit_sha is None or len(manifest.code_commit_sha) == 40


def test_run_manifest_never_fabricates_missing_provenance(business_context, metric_contract, evidence):
    from pathlib import Path

    orch = PipelineOrchestrator(customer_id="x", business_function="y")
    orch.record_business_context(business_context)
    orch.record_metric_contract(metric_contract)
    orch.record_evidence(evidence)
    manifest = orch.build_run_manifest(repo_root=Path("/tmp/definitely-not-a-git-repo-xyz"))
    assert manifest.code_commit_sha is None
    assert manifest.dbt_manifest_hash is None
