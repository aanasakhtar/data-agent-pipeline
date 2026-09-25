#!/usr/bin/env python3
"""
engine/run_affirmative_pipeline.py
=====================================
The affirmative path, proven end to end for the first time: a live
planted-gap database with a real operational problem, a stated customer
target, and a role roster -- run through live L6 evidence execution, a
diagnostic finding, an affirmative AI opportunity, a financial value
calculation, subprocess-isolated verification, and a released finding.

SCOPE, stated precisely: this closes the "we have only ever proved the
refusal path" gap for L6 (live evidence execution), L9-adjacent value
calculation, and L10 (verification) -- all of which are now genuinely
live and independently checkable, exactly like everything else in this
codebase.

L7 (diagnosis) and L8 (AI opportunity) in THIS script are deterministic
HEURISTICS, not LLM calls -- clearly marked below as
`_derive_diagnostic_heuristically` and `_derive_ai_opportunity_heuristically`.
Building real LLM-driven L7/L8 was not part of this delivery's explicit
scope (the four requested modules were: the planted-gap generator, live
L6 execution, the golden eval suite for L4/L5, and this end-to-end
runner) and doing it properly would roughly double this delivery's size.
Treat the diagnostic/opportunity content this script produces as
"structurally correct and internally consistent," not as "what a real L7/L8
agent would conclude" -- those are different claims, and only the first
one is being made here.

L4/L5 (metric contract resolution) uses engine.semantic_resolver when
ANTHROPIC_API_KEY is set; otherwise falls back to the pilot's own
already-verified contract (with the planted scenario's target and
metric_id substituted in) so this script is fully runnable without an
API key, while still exercising L6-L11 for real against a live database.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.schemas import (  # noqa: E402
    AIOpportunityRecord,
    BenchmarkRecord,
    BusinessFunctionContext,
    DiagnosticRecord,
    MetricContract,
    NotDiagnosableFamily,
    TaskCharacteristics,
    ValueAssumptions,
)
from engine.evidence import execute_evidence  # noqa: E402
from engine.orchestrator import PipelineOrchestrator  # noqa: E402
from engine.value import compute_value_record, verify_value_arithmetic  # noqa: E402
from engine.verifier import run_deterministic_verification_subprocess  # noqa: E402

# data-source/generator has a hyphen in its parent directory name, so it
# can't be dot-imported as a package (`data-source.generator...` is a
# syntax error) -- add the generator directory itself to sys.path and
# import the flat module directly instead.
_GENERATOR_DIR = REPO_ROOT / "data-source" / "generator"
if str(_GENERATOR_DIR) not in sys.path:
    sys.path.insert(0, str(_GENERATOR_DIR))
from planted_gap_generator import GroundTruth, build_planted_gap_scenario  # noqa: E402


class AffirmativePipelineError(Exception):
    pass


def _resolve_metric_contract(ground_truth) -> MetricContract:
    """
    Live L4/L5 when a key is available (OpenAI or Anthropic); binds to the
    Verified Query Repository if a pre-verified query exists, ensuring
    production-grade SQL execution against the warehouse.
    """
    metric_id = "planted_gap_order_straight_through_rate"
    v_path = REPO_ROOT / "registry" / "verified_queries" / f"{metric_id}.yml"
    verified_sql = None
    if v_path.exists():
        import yaml
        v_data = yaml.safe_load(v_path.read_text())
        for q in v_data.get("verified_queries", []):
            if q.get("name", "").endswith("_overall"):
                verified_sql = q.get("sql", "").strip()
                break

    if os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"):
        from engine.semantic_resolver import resolve_metric_contract

        semantic_model = {
            "gold.fct_orders": ["order_id", "customer_id", "order_date", "order_status", "order_total", "item_count", "total_quantity"],
            "gold.fct_support_tickets": ["ticket_id", "customer_id", "order_id", "priority", "ticket_status", "category", "csat_score", "created_at", "resolved_at", "resolution_hours"],
            "gold.dim_customers": ["customer_id", "plan_tier", "customer_status", "signup_date"],
        }
        contract = resolve_metric_contract(
            customer_input_text=ground_truth.customer_stated_text,
            semantic_model=semantic_model,
            business_function=ground_truth.business_function,
            metric_id=metric_id,
            version=1,
        )
        verified_dims = []
        if v_path.exists():
            import yaml
            v_data = yaml.safe_load(v_path.read_text())
            for q in v_data.get("verified_queries", []):
                name = q.get("name", "")
                if name.startswith(f"{metric_id}_by_"):
                    dim = name[len(f"{metric_id}_by_"):]
                    verified_dims.append(dim)

        combined_dims = list(contract.dimensions)
        for vd in verified_dims:
            if vd not in combined_dims:
                combined_dims.append(vd)

        updates: Dict[str, Any] = {"dimensions": combined_dims}
        if verified_sql:
            updates["executable_query_template"] = verified_sql
            updates["verified_query_ref"] = f"registry/verified_queries/{metric_id}.yml"

        return contract.model_copy(update=updates)

    pilot_contract = MetricContract.model_validate(
        json.loads((REPO_ROOT / "artifacts/metric_contracts/order_straight_through_rate.json").read_text())
    )
    return pilot_contract.model_copy(
        update={
            "metric_id": metric_id,
            "business_process": ground_truth.business_function,
            "user_goal_text": ground_truth.customer_stated_text,
            "target_value": ground_truth.stated_target_stp,
            "target_source": "customer stated 90% in their goal text",
            "verified_query_ref": f"registry/verified_queries/{metric_id}.yml",
        }
    )


def _derive_diagnostic_heuristically(evidence, ground_truth) -> DiagnosticRecord:
    """
    DETERMINISTIC heuristic, not an LLM call -- see module docstring.
    Finds the worst-performing segment directly from measured
    segment_results and reports it as an OBSERVED (not hypothesized)
    finding, since it's a direct computation from measured data.
    """
    if not evidence.segment_results:
        raise AffirmativePipelineError("no segment_results in evidence -- cannot derive a segment-level diagnostic")

    rate_key = next((k for k in evidence.segment_results[0] if "rate" in k.lower()), None)
    if rate_key is None:
        raise AffirmativePipelineError("could not find a rate column in segment_results")

    worst = min(evidence.segment_results, key=lambda s: s[rate_key])
    best = max(evidence.segment_results, key=lambda s: s[rate_key])
    dimension_key = next(k for k in worst if k != rate_key and not str(k).endswith("orders"))

    return DiagnosticRecord(
        diagnostic_id=f"segment_concentration_{worst[dimension_key]}",
        category="exception_concentration",
        method="min/max segment comparison over live segment_results",
        observation=(
            f"Segment {worst[dimension_key]!r} measures {worst[rate_key]} on "
            f"{evidence.metric_contract_id}, versus {best[dimension_key]!r} at "
            f"{best[rate_key]} -- a gap of {round(best[rate_key] - worst[rate_key], 4)} "
            f"between the best- and worst-performing segments in this evidence pull."
        ),
        interpretation=(
            f"The overall rate ({evidence.observed_value}) is being pulled down "
            f"disproportionately by the {worst[dimension_key]!r} segment specifically, "
            "rather than being uniformly below target across all segments."
        ),
        evidence_ids=[evidence.evidence_id],
        source_queries=[evidence.query],
        affected_segments=[str(worst[dimension_key])],
        severity="high" if (best[rate_key] - worst[rate_key]) > 0.2 else "medium",
        confidence="high -- directly measured from live segment_results, not inferred",
        causal_status="observed",
        counterevidence_ids=[],
        supporting_metrics=[evidence.evidence_id],
        recommended_next_test=(
            f"Trace individual {worst[dimension_key]!r}-segment orders with linked "
            "tickets to identify whether the tickets share a common root cause "
            "(e.g. a specific fulfillment step) before recommending a fix."
        ),
    )


def _derive_ai_opportunity_heuristically(diagnostic: DiagnosticRecord, evidence) -> AIOpportunityRecord:
    """DETERMINISTIC heuristic, not an LLM call -- see module docstring."""
    return AIOpportunityRecord(
        opportunity_id=f"ai_opportunity_{diagnostic.diagnostic_id}",
        linked_metric_gaps=[evidence.metric_contract_id],
        linked_diagnostics=[diagnostic.diagnostic_id],
        process_step=f"Order fulfillment / exception handling for segment {diagnostic.affected_segments[0]}",
        observed_problem=diagnostic.observation,
        evidence_ids=[evidence.evidence_id],
        task_characteristics=TaskCharacteristics(
            repeatability=4,
            data_availability=4,
            determinism=3,
            exception_rate=4,
            judgment_intensity=2,
            error_consequence=2,
            workflow_integration=3,
            governance_sensitivity=2,
        ),
        ai_fit=(
            "High-volume, repeatable order/ticket matching with clear structured "
            "signals (order status, ticket linkage) -- a reasonable BOUNDED_AUTOMATION "
            "candidate: automatically flag and pre-triage tickets for the affected "
            "segment before they reach a human queue."
        ),
        readiness="Segment-level data is directly queryable today; no new data source required.",
        risk_profile="Low-to-medium -- misrouted triage is recoverable, not customer-facing-irreversible.",
        autonomy_level="BOUNDED_AUTOMATION",
        expected_kpi_impact=f"Directly targets the segment driving the gap on {evidence.metric_contract_id}",
        dependencies=["Access to live ticket creation events for the affected segment"],
        human_control_points=["Human review before auto-resolving a ticket, only auto-triage/routing is automated"],
        recommendation_confidence="medium -- derived from a deterministic heuristic standing in for a full L8 pass, not an LLM judgment; see module docstring",
    )


def run_affirmative_pipeline(rebuild_scenario: bool = True) -> PipelineOrchestrator:
    scenario_dir = REPO_ROOT / "data-source" / "generator" / "output" / "planted_gap"
    ground_truth_path = scenario_dir / "scenario_ground_truth.json"

    if rebuild_scenario or not ground_truth_path.exists():
        ground_truth = build_planted_gap_scenario(scenario_dir)
    else:
        raw = json.loads(ground_truth_path.read_text())
        ground_truth = GroundTruth(**raw)

    db_path = scenario_dir / "planted_gap.duckdb"

    orch = PipelineOrchestrator(customer_id="planted-gap-demo", business_function=ground_truth.business_function)

    context = BusinessFunctionContext(
        business_function=ground_truth.business_function,
        use_case="AI adoption gap analysis",
        process_scope="Order fulfillment and post-order support",
        customer_goal=[ground_truth.customer_stated_text],
        stated_current_state="Customer believes Pro-tier orders generate more tickets than expected but has no measured figure.",
        desired_target=[f"{int(ground_truth.stated_target_stp * 100)}% straight-through rate across all plan tiers"],
        time_horizon="current fiscal year",
        organizational_scope="Order fulfillment and customer support teams",
        constraints=[],
        authorized_sources=["gold.fct_orders", "gold.fct_support_tickets", "gold.dim_customers"],
        unresolved_questions=[],
    )
    orch.record_business_context(context)

    contract = _resolve_metric_contract(ground_truth)
    orch.record_metric_contract(contract)

    evidence = execute_evidence(contract, str(db_path), repo_root=REPO_ROOT)
    orch.record_evidence(evidence)

    diagnostic = _derive_diagnostic_heuristically(evidence, ground_truth)
    orch.record_diagnostics([diagnostic])

    ai_opportunity = _derive_ai_opportunity_heuristically(diagnostic, evidence)
    orch.record_ai_opportunity(ai_opportunity)

    # No cross-customer cohort exists for a single synthetic scenario --
    # suppressed honestly rather than fabricating a benchmark.
    benchmark = BenchmarkRecord(
        metric_id=evidence.metric_contract_id,
        benchmark_source="none -- single synthetic customer scenario",
        cohort_definition="n/a",
        cohort_count=0,
        cases_per_cohort=0,
        direction=contract.direction,
        statistic_used="n/a",
        benchmark_value=None,
        stability="n/a",
        comparability="not comparable -- no cohort exists for a planted single-customer demo scenario",
        suppression_reason="no cross-customer cohort available for this scenario",
    )
    orch.record_benchmark(benchmark)

    verification = run_deterministic_verification_subprocess(
        verification_id=f"affirmative-{evidence.evidence_id}",
        evidence_bundle=evidence,
        db_path=str(db_path.resolve()),
        repo_root=REPO_ROOT,
    )
    orch.record_verification(verification)

    if verification.disposition not in ("PASS", "LOW_CONFIDENCE"):
        raise AffirmativePipelineError(
            f"verification did not pass: {verification.disposition} -- {verification.notes}"
        )

    assumptions = ValueAssumptions(**{k: v for k, v in ground_truth.role_roster.items() if k != "role_name"})
    value_record = compute_value_record(
        value_id=f"value_{evidence.evidence_id}",
        metric_contract=contract,
        evidence=evidence,
        assumptions=assumptions,
    )
    value_check = verify_value_arithmetic(value_record, contract, evidence)
    if not value_check.passed:
        raise AffirmativePipelineError(f"value calculation failed independent re-verification: {value_check.detail}")

    from engine.schemas import FindingDraft

    finding = FindingDraft(
        finding_id=f"finding_{evidence.evidence_id}",
        headline=(
            f"{ground_truth.role_roster['role_name']} workload: "
            f"{diagnostic.affected_segments[0]}-tier orders driving a "
            f"{value_record.gap_fraction:.2%} straight-through-rate gap"
        ),
        severity=diagnostic.severity,
        verified_metrics=[evidence.metric_contract_id],
        linked_evidence=[evidence.evidence_id],
        diagnosis=[diagnostic.diagnostic_id],
        benchmark_context="No cross-customer benchmark available for this scenario (suppressed, not fabricated).",
        ai_opportunity=ai_opportunity.ai_fit,
        advisory_match=(
            f"Bounded-automation ticket triage for the {diagnostic.affected_segments[0]} segment "
            f"(autonomy_level={ai_opportunity.autonomy_level})"
        ),
        verification_status=verification.disposition,
        confidence=diagnostic.confidence,
        provenance_chain=[
            f"BusinessFunctionContext ({ground_truth.business_function})",
            f"MetricContract {contract.metric_id} v{contract.version}",
            f"EvidenceBundle {evidence.evidence_id}",
            f"DiagnosticRecord {diagnostic.diagnostic_id}",
            f"AIOpportunityRecord {ai_opportunity.opportunity_id}",
            f"ValueRecord {value_record.value_id}",
            f"VerificationResult {verification.verification_id}",
        ],
    )
    orch.record_finding(finding)

    orch._ground_truth = ground_truth  # type: ignore[attr-defined]  # stashed for the harness/tests to compare against; not part of the orchestrator's real contract
    orch._value_record = value_record  # type: ignore[attr-defined]

    return orch


if __name__ == "__main__":
    orch = run_affirmative_pipeline()
    print(f"Final state: {orch.state.value}")
    print(json.dumps(orch.summary(), indent=2, default=str))
