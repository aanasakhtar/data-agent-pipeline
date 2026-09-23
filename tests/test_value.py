from __future__ import annotations

import pytest

from engine.value import (
    ValueCalculationError,
    compute_gap_fraction,
    compute_value_record,
    verify_value_arithmetic,
)
from engine.schemas import ValueAssumptions


@pytest.fixture
def assumptions() -> ValueAssumptions:
    return ValueAssumptions(
        salary_source=65000,
        overhead_multiplier=1.3,
        headcount=14,
        pct_time_on_function=0.6,
        pct_automatable=0.6,
        realization_mode="blended",
        blended_cash_ratio=0.6,
        realization_factor=0.7,
    )


def test_refuses_to_calculate_with_no_target(metric_contract, evidence, assumptions):
    """The real pilot's own contract has target_value=None. This must
    refuse cleanly, not invent a number."""
    assert metric_contract.target_value is None
    with pytest.raises(ValueCalculationError):
        compute_value_record(
            value_id="v1", metric_contract=metric_contract, evidence=evidence, assumptions=assumptions
        )


def test_gap_is_zero_when_already_past_target(metric_contract, evidence, assumptions):
    """Real observed_value is 0.9047. A target of 0.80 is already
    exceeded -- gap must clamp to 0.0, never go negative."""
    mc = metric_contract.model_copy(update={"target_value": 0.80})
    record = compute_value_record(value_id="v1", metric_contract=mc, evidence=evidence, assumptions=assumptions)
    assert record.gap_fraction == 0.0
    assert record.total_annual_unlock == 0.0
    assert record.cash_benefit == 0.0
    assert record.capacity_benefit == 0.0


def test_real_gap_produces_positive_value(metric_contract, evidence, assumptions):
    mc = metric_contract.model_copy(update={"target_value": 0.95})
    record = compute_value_record(value_id="v2", metric_contract=mc, evidence=evidence, assumptions=assumptions)
    assert record.gap_fraction == pytest.approx(0.95 - 0.9047, abs=1e-3)
    assert record.total_annual_unlock > 0
    assert record.cash_benefit + record.capacity_benefit == pytest.approx(record.total_annual_unlock, abs=0.01)


def test_direction_awareness_lower_is_better(metric_contract, evidence, assumptions):
    """A lower-is-better metric where observed EXCEEDS target (bad) must
    produce a positive gap; where observed is BELOW target (good) must
    clamp to zero -- the opposite sense from higher_is_better."""
    mc = metric_contract.model_copy(update={"direction": "lower_is_better", "target_value": 0.5})
    # observed 0.9047 > target 0.5 -- worse than target, real gap
    record_bad = compute_value_record(value_id="v3", metric_contract=mc, evidence=evidence, assumptions=assumptions)
    assert record_bad.gap_fraction == pytest.approx(0.9047 - 0.5, abs=1e-3)

    mc_good = metric_contract.model_copy(update={"direction": "lower_is_better", "target_value": 0.95})
    # observed 0.9047 < target 0.95 -- already better than target, gap = 0
    record_good = compute_value_record(value_id="v4", metric_contract=mc_good, evidence=evidence, assumptions=assumptions)
    assert record_good.gap_fraction == 0.0


@pytest.mark.parametrize(
    "mode,expected_cash_is_total,expected_capacity_is_total",
    [("cash_only", True, False), ("capacity_only", False, True)],
)
def test_realization_mode_pure_splits(metric_contract, evidence, mode, expected_cash_is_total, expected_capacity_is_total):
    assumptions = ValueAssumptions(
        salary_source=65000, overhead_multiplier=1.3, headcount=14,
        pct_time_on_function=0.6, pct_automatable=0.6, realization_mode=mode,
    )
    mc = metric_contract.model_copy(update={"target_value": 0.95})
    record = compute_value_record(value_id="v5", metric_contract=mc, evidence=evidence, assumptions=assumptions)
    if expected_cash_is_total:
        assert record.cash_benefit == record.total_annual_unlock
        assert record.capacity_benefit == 0.0
    if expected_capacity_is_total:
        assert record.capacity_benefit == record.total_annual_unlock
        assert record.cash_benefit == 0.0


def test_value_record_is_pure_and_reproducible(metric_contract, evidence, assumptions):
    mc = metric_contract.model_copy(update={"target_value": 0.95})
    r1 = compute_value_record(value_id="v6a", metric_contract=mc, evidence=evidence, assumptions=assumptions)
    r2 = compute_value_record(value_id="v6b", metric_contract=mc, evidence=evidence, assumptions=assumptions)
    assert r1.calculation_hash == r2.calculation_hash
    assert r1.total_annual_unlock == r2.total_annual_unlock


def test_verify_value_arithmetic_passes_on_untampered_record(metric_contract, evidence, assumptions):
    mc = metric_contract.model_copy(update={"target_value": 0.95})
    record = compute_value_record(value_id="v7", metric_contract=mc, evidence=evidence, assumptions=assumptions)
    result = verify_value_arithmetic(record, mc, evidence)
    assert result.passed is True


def test_verify_value_arithmetic_catches_tampering(metric_contract, evidence, assumptions):
    mc = metric_contract.model_copy(update={"target_value": 0.95})
    record = compute_value_record(value_id="v8", metric_contract=mc, evidence=evidence, assumptions=assumptions)
    tampered = record.model_copy(update={"total_annual_unlock": record.total_annual_unlock * 100})
    result = verify_value_arithmetic(tampered, mc, evidence)
    assert result.passed is False
    assert "MISMATCH" in result.detail
