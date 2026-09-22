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
    orch = _build_full_run(
        business_context, metric_contract, evidence, diagnostic_exception_concentration,
        diagnostic_process_variant, ai_opportunity, benchmark,
    )
    reject = VerificationResult(
        verification_id="forced-reject",
        checked_records=["x"],
        engine_results=stored_verification.engine_results,
        disposition="REJECT",
        retry_count=0,
        notes="forced for test",
    )
    orch.record_verification(reject)
    assert orch.state == PipelineState.TARGETED_RETRY

    orch.record_verification(reject)
    assert orch.state == PipelineState.TARGETED_RETRY

    orch.record_verification(reject)
    assert orch.state == PipelineState.HUMAN_REVIEW

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
