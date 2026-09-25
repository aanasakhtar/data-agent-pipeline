"""
tests/test_p1.py
==================
Tests for Phase P1: the planted-gap generator, live L6 execution
(engine.evidence), the semantic golden evaluation harness
(evals.golden_eval), the L4/L5 resolver's deterministic scaffolding
(engine.semantic_resolver), and the full affirmative pipeline.

Everything here runs against real data and a real (freshly rebuilt)
planted-gap DuckDB warehouse -- nothing in this file is mocked EXCEPT
the Anthropic client, which is a fake by necessity (no API key was
available while building this; see engine/README.md and
engine/semantic_resolver.py's module docstring for exactly what that
does and doesn't prove).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_GENERATOR_DIR = REPO_ROOT / "data-source" / "generator"
if str(_GENERATOR_DIR) not in sys.path:
    sys.path.insert(0, str(_GENERATOR_DIR))

from engine.evidence import EvidenceExecutionError, execute_evidence  # noqa: E402
from engine.schemas import MetricContract  # noqa: E402
from engine.semantic_resolver import SemanticResolutionError, resolve_metric_contract  # noqa: E402
from engine.value import compute_value_record, verify_value_arithmetic  # noqa: E402
from engine.verifier import run_deterministic_verification  # noqa: E402
from evals.golden_eval import (  # noqa: E402
    GOLDEN_CASES,
    FakeAnthropicMessages,
    evaluate_semantic_accuracy,
    run_golden_eval_suite,
)


@pytest.fixture(scope="session")
def planted_gap_ground_truth():
    from planted_gap_generator import build_planted_gap_scenario

    return build_planted_gap_scenario(REPO_ROOT / "data-source" / "generator" / "output" / "planted_gap")


@pytest.fixture(scope="session")
def planted_gap_db_path(planted_gap_ground_truth) -> str:
    return planted_gap_ground_truth.db_path


@pytest.fixture(scope="session")
def pilot_metric_contract() -> MetricContract:
    import json

    return MetricContract.model_validate(
        json.loads((REPO_ROOT / "artifacts/metric_contracts/order_straight_through_rate.json").read_text())
    )


# ---------------------------------------------------------------------------
# Planted-gap generator
# ---------------------------------------------------------------------------


def test_planted_gap_matches_its_own_ground_truth_file(planted_gap_ground_truth, planted_gap_db_path):
    import duckdb

    con = duckdb.connect(planted_gap_db_path, read_only=True)
    try:
        row = con.execute(
            """
            select count(distinct o.order_id), count(distinct o.order_id) filter (where t.order_id is null)
            from gold.fct_orders o left join gold.fct_support_tickets t on o.order_id = t.order_id
            where o.order_status = 'completed'
            """
        ).fetchone()
    finally:
        con.close()
    assert row[0] == planted_gap_ground_truth.total_completed_orders == 1100
    assert row[1] == planted_gap_ground_truth.total_no_ticket_orders == 948


def test_planted_gap_segment_breakdown_matches_plan(planted_gap_db_path):
    import duckdb

    con = duckdb.connect(planted_gap_db_path, read_only=True)
    try:
        rows = con.execute(
            """
            select c.plan_tier, count(distinct o.order_id),
                   round(count(distinct o.order_id) filter (where t.order_id is null) * 1.0 / count(distinct o.order_id), 4)
            from gold.fct_orders o join gold.dim_customers c on o.customer_id = c.customer_id
            left join gold.fct_support_tickets t on o.order_id = t.order_id
            where o.order_status = 'completed' group by 1 order by 1
            """
        ).fetchall()
    finally:
        con.close()
    by_tier = {r[0]: (r[1], r[2]) for r in rows}
    assert by_tier["enterprise"] == (150, 0.96)
    assert by_tier["free"] == (650, 0.96)
    assert by_tier["pro"] == (300, 0.6)  # the planted concentrated gap


def test_ground_truth_gap_fraction_is_exact(planted_gap_ground_truth):
    assert planted_gap_ground_truth.expected_observed_value == 0.8618
    assert planted_gap_ground_truth.expected_gap_fraction == pytest.approx(0.0382, abs=1e-6)


# ---------------------------------------------------------------------------
# Live L6 execution (engine.evidence)
# ---------------------------------------------------------------------------


def test_live_execution_reproduces_the_recorded_pilot_fixture(pilot_metric_contract):
    """The strongest possible check on evidence.py: running it live
    against the REAL pilot dev.duckdb must reproduce the exact recorded
    pilot values (0.9047 / 965), with zero static JSON involved."""
    db_path = REPO_ROOT / "dbt" / "customer_platform" / "dev.duckdb"
    if not db_path.exists():
        pytest.skip("dev.duckdb not built -- run `dbt build --target local` first")
    bundle = execute_evidence(pilot_metric_contract, str(db_path), repo_root=REPO_ROOT)
    assert bundle.observed_value == pytest.approx(0.9047, abs=1e-4)
    assert bundle.sample_size == 965
    assert bundle.numerator == 873
    assert bundle.denominator == 965
    assert bundle.caveats == []
    assert len(bundle.segment_results) == 3


def test_live_execution_on_planted_gap_matches_ground_truth(pilot_metric_contract, planted_gap_ground_truth, planted_gap_db_path):
    bundle = execute_evidence(pilot_metric_contract, planted_gap_db_path, repo_root=REPO_ROOT)
    assert bundle.observed_value == planted_gap_ground_truth.expected_observed_value
    assert bundle.sample_size == planted_gap_ground_truth.total_completed_orders
    assert bundle.numerator == planted_gap_ground_truth.total_no_ticket_orders


def test_live_execution_bundle_passes_independent_verification(pilot_metric_contract, planted_gap_db_path):
    bundle = execute_evidence(pilot_metric_contract, planted_gap_db_path, repo_root=REPO_ROOT)
    result = run_deterministic_verification(
        verification_id="p1-test", evidence_bundle=bundle, db_path=planted_gap_db_path, repo_root=REPO_ROOT
    )
    assert result.disposition == "PASS"


def test_execute_evidence_raises_on_missing_database(pilot_metric_contract):
    with pytest.raises(EvidenceExecutionError):
        execute_evidence(pilot_metric_contract, "/nonexistent/x.duckdb")


def test_execute_evidence_raises_on_empty_query_template(pilot_metric_contract, planted_gap_db_path):
    bad = pilot_metric_contract.model_copy(update={"executable_query_template": "   "})
    with pytest.raises(EvidenceExecutionError):
        execute_evidence(bad, planted_gap_db_path)


def test_segmentation_skipped_with_caveat_when_registry_entry_missing(pilot_metric_contract, planted_gap_db_path):
    renamed = pilot_metric_contract.model_copy(update={"metric_id": "no_such_metric_in_registry"})
    bundle = execute_evidence(renamed, planted_gap_db_path, repo_root=REPO_ROOT)
    assert bundle.segment_results == []
    assert any("no verified segmented query" in c for c in bundle.caveats)


# ---------------------------------------------------------------------------
# Financial value on live-measured evidence
# ---------------------------------------------------------------------------


def test_value_calculation_on_live_evidence_matches_ground_truth(pilot_metric_contract, planted_gap_ground_truth, planted_gap_db_path):
    from engine.schemas import ValueAssumptions

    contract = pilot_metric_contract.model_copy(update={"target_value": planted_gap_ground_truth.stated_target_stp})
    evidence = execute_evidence(contract, planted_gap_db_path, repo_root=REPO_ROOT)
    assumptions = ValueAssumptions(**{k: v for k, v in planted_gap_ground_truth.role_roster.items() if k != "role_name"})
    record = compute_value_record(value_id="p1-test-value", metric_contract=contract, evidence=evidence, assumptions=assumptions)

    assert record.gap_fraction == pytest.approx(planted_gap_ground_truth.expected_gap_fraction, abs=1e-6)
    assert record.total_annual_unlock == pytest.approx(planted_gap_ground_truth.expected_total_annual_unlock, abs=0.01)
    assert record.cash_benefit == pytest.approx(planted_gap_ground_truth.expected_cash_benefit, abs=0.01)
    assert record.capacity_benefit == pytest.approx(planted_gap_ground_truth.expected_capacity_benefit, abs=0.01)

    check = verify_value_arithmetic(record, contract, evidence)
    assert check.passed is True


# ---------------------------------------------------------------------------
# Semantic resolver scaffolding (fake client -- see module docstring)
# ---------------------------------------------------------------------------


def test_resolver_produces_valid_contract_from_fake_client():
    case = GOLDEN_CASES[0]
    contract = resolve_metric_contract(
        customer_input_text=case.customer_input_text,
        semantic_model={},
        business_function=case.expected_business_function,
        metric_id="test_resolver",
        client=FakeAnthropicMessages(case.reference_llm_response),
    )
    assert contract.resolution_status == "RESOLVED"
    assert contract.metric_id == "test_resolver"  # caller-supplied, not model-supplied
    assert "gold.fct_orders" in contract.source_entities


def test_resolver_rejects_malformed_json():
    class BadClient:
        def create(self, **kw):
            class R:
                content = [type("T", (), {"text": "not json"})()]
            return R()

    with pytest.raises(SemanticResolutionError):
        resolve_metric_contract(
            customer_input_text="x", semantic_model={}, business_function="y",
            metric_id="z", client=BadClient(),
        )


def test_resolver_rejects_response_with_unrequested_fields():
    case = GOLDEN_CASES[0]
    tampered = dict(case.reference_llm_response)
    tampered["metric_id"] = "sneaky"
    with pytest.raises(SemanticResolutionError):
        resolve_metric_contract(
            customer_input_text="x", semantic_model={}, business_function="y",
            metric_id="z", client=FakeAnthropicMessages(tampered),
        )


def test_resolver_rejects_response_missing_required_fields():
    with pytest.raises(SemanticResolutionError):
        resolve_metric_contract(
            customer_input_text="x", semantic_model={}, business_function="y",
            metric_id="z", client=FakeAnthropicMessages({"metric_name": "incomplete"}),
        )


# ---------------------------------------------------------------------------
# Golden evaluation harness
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[c.test_case_id for c in GOLDEN_CASES])
def test_each_golden_case_passes_in_reference_mode(case):
    contract = resolve_metric_contract(
        customer_input_text=case.customer_input_text,
        semantic_model={},
        business_function=case.expected_business_function,
        metric_id=f"golden_{case.test_case_id}",
        client=FakeAnthropicMessages(case.reference_llm_response),
    )
    result = evaluate_semantic_accuracy(contract, case)
    assert result.passed, result.details


def test_golden_eval_suite_reports_4_of_4_in_reference_mode():
    results = run_golden_eval_suite()
    assert len(results) == 4
    assert all(r.passed for r in results)


def test_evaluate_semantic_accuracy_catches_wrong_table():
    case = GOLDEN_CASES[0]
    bad_response = dict(case.reference_llm_response)
    bad_response["source_entities"] = ["gold.fct_support_tickets"]
    produced = resolve_metric_contract(
        customer_input_text=case.customer_input_text, semantic_model={},
        business_function=case.expected_business_function, metric_id="test_wrong_table",
        client=FakeAnthropicMessages(bad_response),
    )
    result = evaluate_semantic_accuracy(produced, case)
    assert result.passed is False
    assert result.table_correct is False


def test_evaluate_semantic_accuracy_catches_false_confidence():
    """A model that claims RESOLVED on a genuinely ambiguous input must
    be caught -- this is the single most important thing the golden
    eval suite needs to be able to detect."""
    ambiguous_case = GOLDEN_CASES[1]
    overconfident_response = GOLDEN_CASES[0].reference_llm_response
    produced = resolve_metric_contract(
        customer_input_text=ambiguous_case.customer_input_text, semantic_model={},
        business_function=ambiguous_case.expected_business_function, metric_id="test_overconfident",
        client=FakeAnthropicMessages(overconfident_response),
    )
    result = evaluate_semantic_accuracy(produced, ambiguous_case)
    assert result.passed is False
    assert result.status_correct is False


def test_evaluate_semantic_accuracy_catches_sneaky_query_on_unresolved_status():
    from evals.golden_eval import _unresolved_reference

    case = GOLDEN_CASES[1]
    sneaky = _unresolved_reference("AMBIGUOUS_NEEDS_INPUT", "vague")
    sneaky["executable_query_template"] = "select 1"
    produced = resolve_metric_contract(
        customer_input_text=case.customer_input_text, semantic_model={},
        business_function=case.expected_business_function, metric_id="test_sneaky",
        client=FakeAnthropicMessages(sneaky),
    )
    result = evaluate_semantic_accuracy(produced, case)
    assert result.passed is False


# ---------------------------------------------------------------------------
# Full affirmative pipeline, end to end
# ---------------------------------------------------------------------------


def test_full_affirmative_pipeline_reaches_finding_released():
    from engine.orchestrator import PipelineState
    from engine.run_affirmative_pipeline import run_affirmative_pipeline

    orch = run_affirmative_pipeline()
    assert orch.state == PipelineState.FINDING_RELEASED
    assert orch._verification_retry_count == 0


def test_full_affirmative_pipeline_matches_ground_truth_exactly():
    from engine.run_affirmative_pipeline import run_affirmative_pipeline

    orch = run_affirmative_pipeline()
    gt = orch._ground_truth
    vr = orch._value_record

    assert orch._evidence.observed_value == gt.expected_observed_value
    assert vr.gap_fraction == pytest.approx(gt.expected_gap_fraction, abs=1e-6)
    assert vr.total_annual_unlock == pytest.approx(gt.expected_total_annual_unlock, abs=0.01)
    assert vr.cash_benefit == pytest.approx(gt.expected_cash_benefit, abs=0.01)
    assert vr.capacity_benefit == pytest.approx(gt.expected_capacity_benefit, abs=0.01)


def test_full_affirmative_pipeline_finding_has_complete_provenance_chain():
    from engine.run_affirmative_pipeline import run_affirmative_pipeline

    orch = run_affirmative_pipeline()
    finding = orch._finding
    assert len(finding.provenance_chain) == 7
    assert finding.verification_status == "PASS"
    assert finding.severity in ("low", "medium", "high", "critical")


def test_full_affirmative_pipeline_diagnostic_targets_the_planted_segment():
    from engine.run_affirmative_pipeline import run_affirmative_pipeline

    orch = run_affirmative_pipeline()
    diagnostic = orch._diagnostics[0]
    assert diagnostic.affected_segments == ["pro"]  # the planted concentrated gap
    assert diagnostic.causal_status == "observed"
