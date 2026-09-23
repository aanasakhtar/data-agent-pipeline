"""
engine/gates.py
================
Cross-cutting deterministic gates, per blueprint section 5: check a
MetricContract or EvidenceBundle for basic well-formedness the moment
it's produced, rather than waiting until the end of an 8-layer chain to
discover the metric was never resolvable in the first place.

Pydantic's own type/Literal constraints already enforce STRUCTURAL
presence (a MetricContract without a `direction` cannot even be
constructed). These functions check what Pydantic can't: is the contract
SEMANTICALLY ready to proceed, is the evidence's sample size actually
sufficient per the contract's OWN stated guidance.

Intentionally cheap: no LLM, no DB access. That's the entire point of a
cross-cutting plane instead of one expensive gate at the very end --
these run on every record without meaningfully adding to run cost.
"""

from __future__ import annotations

import re
from typing import Optional

from engine.schemas import EvidenceBundle, MetricContract


def parse_minimum_sample_size(guidance_text: str) -> Optional[int]:
    """
    Best-effort extraction of a numeric sample-size threshold from a
    MetricContract's free-text `minimum_sample_guidance` field (e.g. "at
    least 50 completed orders for the rate to be reportable at HIGH
    confidence" -> 50).

    Honest limitation: this takes the FIRST integer found in the string,
    which is correct for the one real example in this repo but will
    misparse a sentence structured differently (e.g. one that mentions a
    percentage before the count). Recommendation flagged in
    engine/README.md: promote this to a structured
    `minimum_sample_size: int` field on MetricContract in a future
    schema version rather than continuing to parse prose.
    """
    match = re.search(r"\d+", guidance_text)
    return int(match.group()) if match else None


def metric_contract_gate(contract: MetricContract) -> Optional[str]:
    """
    Returns None if the contract may proceed to L6 (evidence
    measurement), else a human-readable reason it cannot. Pure function
    -- the orchestrator decides what to do with the reason (raise); a
    batch job might instead log it and skip the metric.
    """
    if not contract.is_measurable:
        return (
            f"resolution_status={contract.resolution_status!r} blocks "
            f"measurement (resolution_notes={contract.resolution_notes!r})"
        )
    if not contract.numerator_definition.strip():
        return "numerator_definition is empty"
    if not contract.denominator_definition.strip():
        return "denominator_definition is empty"
    if not contract.executable_query_template.strip():
        return "executable_query_template is empty -- cannot proceed to L6 with no query"
    return None


def evidence_quality_gate(evidence: EvidenceBundle, contract: MetricContract) -> Optional[str]:
    """Returns None if the evidence may proceed past L6, else a reason."""
    if evidence.data_quality_status == "UNUSABLE":
        return f"data_quality_status=UNUSABLE for evidence_id={evidence.evidence_id!r}"

    min_sample = parse_minimum_sample_size(contract.minimum_sample_guidance)
    if min_sample is not None and evidence.sample_size < min_sample:
        return (
            f"sample_size={evidence.sample_size} is below the contract's "
            f"minimum_sample_guidance (parsed threshold: {min_sample})"
        )
    return None
