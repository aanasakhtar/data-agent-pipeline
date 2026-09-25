"""
evals/golden_eval.py
======================
The Semantic Golden Evaluation Suite: checks whether L4/L5 (see
engine.semantic_resolver) understood a customer's free-text goal
correctly -- did it target the right physical table, define numerator/
denominator, pick the right direction, and correctly refuse to guess
when the goal is ambiguous or unsupported by the schema. This is
distinct from and complementary to L10's runtime verification: L10
checks whether the DuckDB math matches the recorded query; this checks
whether the query was ever asking the right question in the first
place.

TWO MODES, and this matters for reading the scorecard correctly:

  LIVE mode (a real `client` is supplied, e.g. `anthropic.Anthropic()`
  with a valid ANTHROPIC_API_KEY): each golden case's customer_input_text
  is actually sent to the model, and evaluate_semantic_accuracy grades
  its REAL output. This is the mode that actually tests L4/L5's semantic
  understanding.

  REFERENCE mode (default, no client): each golden case's
  reference_llm_response (a human-curated "what a correct L4/L5 should
  produce for this input") is fed through a fake client instead of a
  real model call. This mode tests that evaluate_semantic_accuracy's
  GRADING LOGIC is itself correct -- it proves the harness would catch
  a wrong answer if it saw one, not that the real model gives right
  answers. No API key was available while building this, so REFERENCE
  mode is the only mode that was actually run. See engine/README.md.

Run directly for a scorecard in whichever mode is available:
    python evals/golden_eval.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(dotenv_path=_REPO_ROOT / ".env")

from pydantic import BaseModel, ConfigDict

from engine.schemas import MetricContract, ResolutionStatus
from engine.semantic_resolver import resolve_metric_contract


class GoldenCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_case_id: str
    customer_input_text: str
    expected_business_function: str
    expected_primary_table: str
    expected_metric_name: Optional[str] = None
    expected_direction: Optional[str] = None  # "higher_is_better" | "lower_is_better" | None when not applicable
    expected_status: ResolutionStatus
    expected_gap_range: Optional[List[float]] = None  # [min, max] -- consumed downstream by run_affirmative_pipeline, not by evaluate_semantic_accuracy

    # REFERENCE mode support: a human-curated "correct" LLM output for
    # this input. Every key in engine.semantic_resolver._LLM_OWNED_FIELDS
    # must be present, exactly as a real model response would need to be.
    reference_llm_response: Dict[str, Any]


@dataclass
class EvalCaseResult:
    test_case_id: str
    passed: bool
    status_correct: bool
    table_correct: Optional[bool]
    direction_correct: Optional[bool]
    numerator_denominator_defined: Optional[bool]
    details: List[str] = field(default_factory=list)


def evaluate_semantic_accuracy(produced_contract: MetricContract, golden_case: GoldenCase) -> EvalCaseResult:
    """
    Grades ONE produced MetricContract against ONE golden case.
    Deliberately takes only these two arguments (matching the requested
    signature) -- schema-grounding (did the model only reference tables
    that actually exist) is enforced upstream, at prompt-construction and
    response-validation time in engine.semantic_resolver, not re-checked
    here.
    """
    details: List[str] = []

    status_correct = produced_contract.resolution_status == golden_case.expected_status
    details.append(
        f"resolution_status: produced={produced_contract.resolution_status!r} "
        f"expected={golden_case.expected_status!r} -> {'OK' if status_correct else 'MISMATCH'}"
    )

    table_correct: Optional[bool] = None
    direction_correct: Optional[bool] = None
    numerator_denominator_defined: Optional[bool] = None

    resolved_like = golden_case.expected_status in ("RESOLVED", "RESOLVED_WITH_ASSUMPTION")

    if resolved_like:
        table_correct = golden_case.expected_primary_table in produced_contract.source_entities
        details.append(
            f"primary table {golden_case.expected_primary_table!r} in "
            f"source_entities={produced_contract.source_entities} -> "
            f"{'OK' if table_correct else 'MISMATCH'}"
        )

        if golden_case.expected_direction is not None:
            direction_correct = produced_contract.direction == golden_case.expected_direction
            details.append(
                f"direction: produced={produced_contract.direction!r} "
                f"expected={golden_case.expected_direction!r} -> "
                f"{'OK' if direction_correct else 'MISMATCH'}"
            )

        numerator_denominator_defined = bool(
            produced_contract.numerator_definition.strip()
        ) and bool(produced_contract.denominator_definition.strip())
        details.append(
            "numerator_definition and denominator_definition both non-empty: "
            f"{'OK' if numerator_denominator_defined else 'MISSING'}"
        )

        if not produced_contract.executable_query_template.strip():
            details.append("WARNING: resolved status but executable_query_template is empty")
    else:
        details.append(f"expected_status={golden_case.expected_status!r} blocks measurement -- table/direction checks not applicable")
        if produced_contract.executable_query_template.strip():
            details.append(
                "MISMATCH: non-resolved status still produced a non-empty "
                "executable_query_template -- a correct L4/L5 must not guess "
                "a query when it hasn't actually resolved the goal"
            )
            status_correct = False  # this is a real semantic failure, not just a formality

    applicable_checks = [c for c in (table_correct, direction_correct, numerator_denominator_defined) if c is not None]
    passed = status_correct and all(applicable_checks)

    return EvalCaseResult(
        test_case_id=golden_case.test_case_id,
        passed=passed,
        status_correct=status_correct,
        table_correct=table_correct,
        direction_correct=direction_correct,
        numerator_denominator_defined=numerator_denominator_defined,
        details=details,
    )


# ---------------------------------------------------------------------------
# Fake client for REFERENCE mode -- see module docstring
# ---------------------------------------------------------------------------


class _FakeTextBlock:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.content = [_FakeTextBlock(text)]


class FakeAnthropicMessages:
    """
    Minimal structural stand-in for `anthropic.Anthropic().messages` --
    implements only `.create(...)`, returning a canned JSON payload
    regardless of what prompt it's given. Used to test
    engine.semantic_resolver's scaffolding (and this eval harness's
    grading logic) without a live API key.
    """

    def __init__(self, canned_response: Dict[str, Any]) -> None:
        self._canned_response = canned_response

    def create(self, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse(json.dumps(self._canned_response))


# ---------------------------------------------------------------------------
# Golden cases
# ---------------------------------------------------------------------------

_REAL_STP_QUERY = (
    "select count(distinct o.order_id) as completed_orders, "
    "count(distinct o.order_id) filter (where t.order_id is null) as no_ticket_orders, "
    "round(count(distinct o.order_id) filter (where t.order_id is null) * 1.0 / "
    "count(distinct o.order_id), 4) as straight_through_rate "
    "from gold.fct_orders o left join gold.fct_support_tickets t on o.order_id = t.order_id "
    "where o.order_status = 'completed'"
)


def _resolved_reference(**overrides: Any) -> Dict[str, Any]:
    """A syntactically-complete RESOLVED reference response, so each
    golden case only needs to override what's specific to it."""
    base: Dict[str, Any] = {
        "metric_name": "Order Straight-Through Rate",
        "user_goal_text": "Increase straight-through order completion (no ticket needed)",
        "semantic_definition": "Share of completed orders with zero linked support tickets, over all completed orders",
        "direction": "higher_is_better",
        "numerator_definition": "count(distinct fct_orders.order_id) where order_status = 'completed' and no linked support ticket",
        "denominator_definition": "count(distinct fct_orders.order_id) where order_status = 'completed'",
        "grain": "single value over the full dataset time window; also broken out by plan_tier",
        "unit": "percent (0.0-1.0)",
        "time_window": "full available history",
        "inclusion_rules": ["order_status = 'completed'"],
        "exclusion_rules": ["orders with status pending/cancelled/refunded excluded"],
        "dimensions": ["plan_tier"],
        "target_value": None,
        "target_source": "not specified by customer",
        "source_entities": ["gold.fct_orders", "gold.fct_support_tickets"],
        "gold_fields": ["fct_orders.order_id", "fct_orders.order_status", "fct_support_tickets.order_id"],
        "executable_query_template": _REAL_STP_QUERY,
        "expected_result_shape": "single row: completed_orders (int), no_ticket_orders (int), straight_through_rate (float 0.0-1.0)",
        "data_quality_requirements": ["fct_orders.order_id not null and unique"],
        "minimum_sample_guidance": "at least 50 completed orders for the rate to be reportable at HIGH confidence",
        "resolution_status": "RESOLVED",
        "resolution_notes": None,
    }
    base.update(overrides)
    return base


def _unresolved_reference(status: str, notes: str) -> Dict[str, Any]:
    """A syntactically-complete non-RESOLVED reference response -- every
    field still needs a value (the resolver requires all keys present),
    just empty/neutral ones where semantically not applicable."""
    return {
        "metric_name": "",
        "user_goal_text": "",
        "semantic_definition": "",
        "direction": "higher_is_better",  # placeholder; not meaningful when unresolved
        "numerator_definition": "",
        "denominator_definition": "",
        "grain": "",
        "unit": "",
        "time_window": "",
        "inclusion_rules": [],
        "exclusion_rules": [],
        "dimensions": [],
        "target_value": None,
        "target_source": "",
        "source_entities": [],
        "gold_fields": [],
        "executable_query_template": "",
        "expected_result_shape": "",
        "data_quality_requirements": [],
        "minimum_sample_guidance": "",
        "resolution_status": status,
        "resolution_notes": notes,
    }


GOLDEN_CASES: List[GoldenCase] = [
    GoldenCase(
        test_case_id="affirmative_planted_gap",
        customer_input_text=(
            "We want our straight-through order processing rate at 90% across all "
            "plan tiers -- right now it feels like our Pro-tier orders are "
            "generating a lot more support tickets than they should, but we don't "
            "have hard numbers on it."
        ),
        expected_business_function="Order Fulfillment & Support (Planted-Gap Scenario)",
        expected_primary_table="gold.fct_orders",
        expected_metric_name="Order Straight-Through Rate",
        expected_direction="higher_is_better",
        expected_status="RESOLVED",
        expected_gap_range=[0.03, 0.05],  # ground truth is exactly 0.0382 -- see planted_gap_generator.py
        reference_llm_response=_resolved_reference(target_value=0.90, target_source="customer stated 90% in their goal text"),
    ),
    GoldenCase(
        test_case_id="vague_ambiguous_goal",
        customer_input_text="We want things to be faster and better for our customers.",
        expected_business_function="Order Fulfillment & Support",
        expected_primary_table="",
        expected_status="AMBIGUOUS_NEEDS_INPUT",
        reference_llm_response=_unresolved_reference(
            "AMBIGUOUS_NEEDS_INPUT",
            "The goal does not specify which process, which metric ('faster' could "
            "mean order cycle time, ticket resolution time, or something else "
            "entirely), or which direction of improvement is being asked for beyond "
            "the word 'better'. Needs the customer to name a specific process step "
            "and metric before a contract can be resolved.",
        ),
    ),
    GoldenCase(
        test_case_id="unmeasurable_goal",
        customer_input_text=(
            "We want to improve our customers' onboarding experience score and "
            "reduce churn caused by a confusing first-week experience."
        ),
        expected_business_function="Order Fulfillment & Support",
        expected_primary_table="",
        expected_status="UNSUPPORTED_BY_AVAILABLE_DATA",
        reference_llm_response=_unresolved_reference(
            "UNSUPPORTED_BY_AVAILABLE_DATA",
            "No onboarding-experience score, churn flag, or first-week-activity "
            "concept exists anywhere in the available gold-layer schema "
            "(gold.fct_orders, gold.fct_support_tickets, gold.dim_customers). "
            "This would require a new data source, not a different query.",
        ),
    ),
    GoldenCase(
        test_case_id="pilot_baseline",
        customer_input_text="Increase straight-through order completion (no ticket needed)",
        expected_business_function="Order Fulfillment & Support",
        expected_primary_table="gold.fct_orders",
        expected_metric_name="Order Straight-Through Rate",
        expected_direction="higher_is_better",
        expected_status="RESOLVED",
        reference_llm_response=_resolved_reference(),  # matches the real pilot contract's actual fields
    ),
]


SEMANTIC_MODEL = {
    "gold.fct_orders": ["order_id", "customer_id", "order_date", "order_status", "order_total", "item_count", "total_quantity"],
    "gold.fct_support_tickets": ["ticket_id", "customer_id", "order_id", "priority", "ticket_status", "category", "csat_score", "created_at", "resolved_at", "resolution_hours"],
    "gold.dim_customers": ["customer_id", "plan_tier", "customer_status", "signup_date"],
}


def run_golden_eval_suite(
    cases: Optional[List[GoldenCase]] = None,
    client: Optional[Any] = None,
    metric_id_prefix: str = "golden",
    live: bool = False,
) -> List[EvalCaseResult]:
    """
    Runs every golden case and returns per-case results. If `live` is True,
    it uses the real configured LLM (OpenAI/Anthropic). If `client` is
    provided, it uses that client. If neither, it runs in REFERENCE mode
    via FakeAnthropicMessages.
    """
    cases = cases if cases is not None else GOLDEN_CASES
    results: List[EvalCaseResult] = []

    shared_client = None
    if live and client is None:
        from engine.semantic_resolver import _get_default_client
        shared_client = _get_default_client()

    for i, case in enumerate(cases):
        if live:
            case_client = client or shared_client
        else:
            case_client = client or FakeAnthropicMessages(case.reference_llm_response)

        try:
            produced = resolve_metric_contract(
                customer_input_text=case.customer_input_text,
                semantic_model=SEMANTIC_MODEL,
                business_function=case.expected_business_function,
                metric_id=f"{metric_id_prefix}_{case.test_case_id}",
                version=1,
                client=case_client,
            )
        except Exception as exc:  # noqa: BLE001 -- an operational failure IS a failed case, not a crash of the suite
            results.append(
                EvalCaseResult(
                    test_case_id=case.test_case_id,
                    passed=False,
                    status_correct=False,
                    table_correct=None,
                    direction_correct=None,
                    numerator_denominator_defined=None,
                    details=[f"resolve_metric_contract raised: {exc}"],
                )
            )
            continue

        results.append(evaluate_semantic_accuracy(produced, case))

    return results


def print_scorecard(results: List[EvalCaseResult], mode: str) -> None:
    print(f"=== Golden Evaluation Scorecard ({mode} mode) ===")
    passed = sum(1 for r in results if r.passed)
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.test_case_id}")
        for d in r.details:
            print(f"      - {d}")
    print(f"  {passed}/{len(results)} cases passed")


if __name__ == "__main__":
    import argparse
    import os
    from engine.semantic_resolver import get_resolver_config

    parser = argparse.ArgumentParser(description="Semantic Golden Evaluation Suite")
    parser.add_argument("--live", action="store_true", help="Run in LIVE mode with real API calls")
    parser.add_argument("--reference", action="store_true", help="Run in REFERENCE mode with canned test fixtures")
    args = parser.parse_args()

    provider, model = get_resolver_config()
    has_keys = bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))

    if args.reference or (not args.live and not has_keys):
        print("Running in REFERENCE mode (canned fixtures)...\n")
        ref_results = run_golden_eval_suite(live=False)
        print_scorecard(ref_results, mode="REFERENCE")
    else:
        print(f"Running LIVE evaluation using provider={provider} model={model}...\n")
        live_results = run_golden_eval_suite(live=True)
        print_scorecard(live_results, mode=f"LIVE ({provider}/{model})")
