from __future__ import annotations

from engine.gates import evidence_quality_gate, metric_contract_gate, parse_minimum_sample_size


def test_real_metric_contract_passes_gate(metric_contract):
    assert metric_contract_gate(metric_contract) is None


def test_real_evidence_passes_gate(evidence, metric_contract):
    assert evidence_quality_gate(evidence, metric_contract) is None


def test_ambiguous_resolution_status_blocks(metric_contract):
    bad = metric_contract.model_copy(update={"resolution_status": "AMBIGUOUS_NEEDS_INPUT"})
    reason = metric_contract_gate(bad)
    assert reason is not None
    assert "AMBIGUOUS_NEEDS_INPUT" in reason


def test_not_measurable_blocks(metric_contract):
    bad = metric_contract.model_copy(update={"resolution_status": "NOT_MEASURABLE"})
    assert metric_contract_gate(bad) is not None


def test_empty_query_template_blocks(metric_contract):
    bad = metric_contract.model_copy(update={"executable_query_template": "   "})
    reason = metric_contract_gate(bad)
    assert reason is not None
    assert "executable_query_template" in reason


def test_unusable_data_quality_blocks(evidence, metric_contract):
    bad = evidence.model_copy(update={"data_quality_status": "UNUSABLE"})
    reason = evidence_quality_gate(bad, metric_contract)
    assert reason is not None
    assert "UNUSABLE" in reason


def test_sample_size_below_minimum_blocks(evidence, metric_contract):
    bad = evidence.model_copy(update={"sample_size": 3})
    reason = evidence_quality_gate(bad, metric_contract)
    assert reason is not None
    assert "sample_size=3" in reason


def test_parse_minimum_sample_size_on_real_guidance_text(metric_contract):
    # documents the actual real string this was written against
    n = parse_minimum_sample_size(metric_contract.minimum_sample_guidance)
    assert n == 50


def test_parse_minimum_sample_size_returns_none_when_no_number_present():
    assert parse_minimum_sample_size("no threshold mentioned here") is None
