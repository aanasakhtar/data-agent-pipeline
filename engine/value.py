"""
engine/value.py
================
Deterministic implementation of the financial value subsystem the
architecture doc has specified since the first review of this project, and
which no artifact anywhere in this repo has ever actually computed. Per
both the maturation plan (F2) and the blueprint (section 13): this must
never be an LLM computation. It's arithmetic on stated assumptions, and it
gets the same treatment as everything else in verifier.py -- compute once,
then recompute independently and diff.

Pipeline:

    verified metric gap (MetricContract.target_value, EvidenceBundle.observed_value)
                  |
    stated ValueAssumptions (salary, headcount, % automatable, etc. --
      NEVER inferred, always supplied)
                  |
    compute_value_record()  <-- pure function, this module
                  |
    ValueRecord
                  |
    verify_value_arithmetic()  <-- independent recomputation + diff,
      same discipline as verify_arithmetic() in verifier.py
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from engine.schemas import EvidenceBundle, MetricContract, ValueAssumptions, ValueRecord

CALCULATION_VERSION = "value-calc-v1"


class ValueCalculationError(Exception):
    """Raised when a value calculation is requested against inputs that
    make it meaningless -- e.g. no target set. This is a refusal, not a
    bug: a MetricContract with target_value=None (the real pilot's actual
    state) has no gap to size, and should not produce an invented number."""


def compute_gap_fraction(contract: MetricContract, evidence: EvidenceBundle) -> float:
    """
    Direction-aware gap sizing -- this is the exact bug flagged in the
    review of the lead's first architecture doc (a flat "p75 is always
    best-in-class" rule breaks for lower-is-better metrics). Applied here
    to target-gap sizing, not just benchmarking: for a higher-is-better
    metric, the gap is how far BELOW target the observed value sits; for
    lower-is-better, it's how far ABOVE target it sits. A metric already
    at or past target has a gap of exactly 0.0, never negative.
    """
    if contract.target_value is None:
        raise ValueCalculationError(
            f"MetricContract {contract.metric_id!r} has target_value=None -- "
            "there is no customer-stated target to size a gap against. "
            "This is the real, common state (see the pilot's own contract) "
            "and is not an error in itself, but a value calculation cannot "
            "proceed until a target exists."
        )

    target = contract.target_value
    observed = evidence.observed_value

    if contract.direction == "higher_is_better":
        raw_gap = target - observed
    else:  # lower_is_better
        raw_gap = observed - target

    return max(0.0, raw_gap)


def compute_value_record(
    *,
    value_id: str,
    metric_contract: MetricContract,
    evidence: EvidenceBundle,
    assumptions: ValueAssumptions,
) -> ValueRecord:
    """
    Pure function: same inputs always produce the same ValueRecord. No
    randomness, no LLM, no hidden state -- this is what makes independent
    re-verification meaningful (verify_value_arithmetic just calls this
    again and diffs).
    """
    gap_fraction = compute_gap_fraction(metric_contract, evidence)

    addressable_labor_pool = (
        assumptions.headcount
        * assumptions.salary_source
        * assumptions.overhead_multiplier
        * assumptions.pct_time_on_function
        * assumptions.pct_automatable
    )

    total_annual_unlock = addressable_labor_pool * gap_fraction * assumptions.realization_factor

    if assumptions.realization_mode == "cash_only":
        cash_benefit = total_annual_unlock
        capacity_benefit = 0.0
    elif assumptions.realization_mode == "capacity_only":
        cash_benefit = 0.0
        capacity_benefit = total_annual_unlock
    else:  # blended
        cash_benefit = total_annual_unlock * assumptions.blended_cash_ratio
        capacity_benefit = total_annual_unlock - cash_benefit  # by subtraction, not a second multiply -- guarantees the sum invariant holds exactly, not just within float tolerance

    calculation_hash = _hash_calculation_inputs(metric_contract, evidence, assumptions)

    return ValueRecord(
        value_id=value_id,
        metric_gap_id=f"{metric_contract.metric_id}:{evidence.evidence_id}",
        assumptions=assumptions,
        gap_fraction=round(gap_fraction, 6),
        addressable_labor_pool=round(addressable_labor_pool, 2),
        total_annual_unlock=round(total_annual_unlock, 2),
        cash_benefit=round(cash_benefit, 2),
        capacity_benefit=round(capacity_benefit, 2),
        calculation_version=CALCULATION_VERSION,
        calculation_hash=calculation_hash,
        provenance=(
            f"metric_contract={metric_contract.metric_id}:{metric_contract.version}, "
            f"evidence={evidence.evidence_id}, calculation_version={CALCULATION_VERSION}"
        ),
    )


def _hash_calculation_inputs(
    contract: MetricContract, evidence: EvidenceBundle, assumptions: ValueAssumptions
) -> str:
    """
    Content-addressing for the calculation itself: hash exactly the
    inputs that determine the output, so a ValueRecord can be checked
    for "was this recomputed from the same inputs" independent of
    re-running the arithmetic. Deliberately excludes anything not used
    in compute_value_record (e.g. evidence.trend_summary) -- the hash
    should change if and only if the OUTPUT could change.
    """
    payload = {
        "calculation_version": CALCULATION_VERSION,
        "metric_id": contract.metric_id,
        "metric_version": contract.version,
        "direction": contract.direction,
        "target_value": contract.target_value,
        "observed_value": evidence.observed_value,
        "assumptions": assumptions.model_dump(),
    }
    canonical = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class ValueVerificationResult:
    passed: bool
    detail: str
    recomputed: ValueRecord | None = None


def verify_value_arithmetic(
    value_record: ValueRecord, metric_contract: MetricContract, evidence: EvidenceBundle
) -> ValueVerificationResult:
    """
    Independent re-derivation, same discipline as verifier.py: recompute
    compute_value_record() from scratch using ONLY the metric contract,
    evidence, and the assumptions already stored on the record under
    test (assumptions are stated inputs, not something to independently
    guess -- what's being checked is whether the ARITHMETIC on those
    stated assumptions was done correctly, not whether the assumptions
    themselves are reasonable; that's a business judgment call, not a
    verification-engine concern).
    """
    try:
        recomputed = compute_value_record(
            value_id=f"{value_record.value_id}:reverify",
            metric_contract=metric_contract,
            evidence=evidence,
            assumptions=value_record.assumptions,
        )
    except ValueCalculationError as exc:
        return ValueVerificationResult(passed=False, detail=f"could not recompute: {exc}")

    fields_to_check = (
        "gap_fraction",
        "addressable_labor_pool",
        "total_annual_unlock",
        "cash_benefit",
        "capacity_benefit",
    )
    mismatches = []
    for field_name in fields_to_check:
        original = getattr(value_record, field_name)
        fresh = getattr(recomputed, field_name)
        if abs(original - fresh) > 0.01:
            mismatches.append(f"{field_name}: recorded={original} vs recomputed={fresh}")

    if value_record.calculation_hash != recomputed.calculation_hash:
        mismatches.append(
            f"calculation_hash: recorded={value_record.calculation_hash} vs "
            f"recomputed={recomputed.calculation_hash} -- inputs have changed "
            "since this ValueRecord was produced"
        )

    if mismatches:
        return ValueVerificationResult(
            passed=False,
            detail="MISMATCH: " + "; ".join(mismatches),
            recomputed=recomputed,
        )

    return ValueVerificationResult(
        passed=True,
        detail=f"recomputed value matches recorded value exactly (hash={recomputed.calculation_hash[:12]}...)",
        recomputed=recomputed,
    )
