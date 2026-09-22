"""
Every fixture used here is a REAL file from artifacts/, not a synthetic
example -- if these pass, the schemas are guaranteed compatible with the
one pilot run that actually exists.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from engine.schemas import EvidenceBundle, FindingDraft, parse_versioned_metric_id


def test_all_real_fixtures_parse_clean(
    business_context, metric_contract, evidence, diagnostic_exception_concentration,
    diagnostic_process_variant, ai_opportunity, benchmark, stored_verification, finding,
):
    """If this test collects and passes at all, all 9 real fixtures parsed
    with zero validation errors (fixture loading happens at collection)."""
    assert business_context.business_function == "Order Fulfillment & Support"
    assert metric_contract.metric_id == "order_straight_through_rate"
    assert evidence.observed_value == pytest.approx(0.9047, abs=1e-4)
    assert diagnostic_exception_concentration.causal_status == "hypothesis"
    assert diagnostic_process_variant.causal_status == "observed"
    assert ai_opportunity.ai_fit == "NO_AI_RECOMMENDATION"
    assert ai_opportunity.is_ai_recommended is False
    assert benchmark.is_suppressed is True
    assert stored_verification.disposition == "PASS"
    assert finding.finding_id == "order-straight-through-rate-pilot-1"


def test_diagnostic_confidence_is_free_text_not_enum(diagnostic_process_variant):
    """Regression guard for the specific design decision in the module
    docstring: this real record's confidence field is a full sentence,
    not a low/medium/high token. If someone "cleans up" the schema later
    by making this a Literal, this test is what breaks and explains why."""
    assert len(diagnostic_process_variant.confidence) > 20
    assert "V4 count" in diagnostic_process_variant.confidence


def test_evidence_query_hash_integrity_accepts_real_data(evidence):
    assert evidence.query_hash  # already validated at parse time; this is just a sanity echo


def test_evidence_query_hash_integrity_rejects_tampering():
    import json
    from pathlib import Path

    raw = json.loads(
        (Path(__file__).resolve().parent.parent / "artifacts/evidence/order_straight_through_rate_20260918T161600Z.json").read_text()
    )
    raw["query"] = raw["query"].replace("completed", "cancelled")
    with pytest.raises(ValidationError, match="query_hash does not match"):
        EvidenceBundle.model_validate(raw)


def test_finding_requires_nonempty_provenance_chain(finding):
    data = finding.model_dump()
    data["provenance_chain"] = []
    with pytest.raises(ValidationError, match="provenance_chain is empty"):
        FindingDraft.model_validate(data)


@pytest.mark.parametrize(
    "value,expected_base,expected_version",
    [
        ("order_straight_through_rate:1", "order_straight_through_rate", 1),
        ("order_straight_through_rate", "order_straight_through_rate", None),
        ("some_metric:12", "some_metric", 12),
        ("weird:name:3", "weird:name", 3),
    ],
)
def test_parse_versioned_metric_id(value, expected_base, expected_version):
    base, version = parse_versioned_metric_id(value)
    assert base == expected_base
    assert version == expected_version


def test_strict_schema_rejects_unknown_field(metric_contract):
    """extra='forbid' is a deliberate choice (see StrictArtifact docstring)
    -- confirm it actually forbids, not just documents intent."""
    from engine.schemas import MetricContract

    data = metric_contract.model_dump()
    data["totally_made_up_field"] = "should not be allowed"
    with pytest.raises(ValidationError):
        MetricContract.model_validate(data)
