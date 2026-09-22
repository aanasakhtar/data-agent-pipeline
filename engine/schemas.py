"""
engine/schemas.py
==================
Strict Pydantic v2 models for the 8 Platinum reasoning artifacts:

    BusinessFunctionContext -> MetricContract -> EvidenceBundle
    -> DiagnosticRecord (N) -> AIOpportunityRecord -> BenchmarkRecord
    -> VerificationResult -> FindingDraft

These are deliberately written against the CURRENT on-disk artifact shape
(everything under artifacts/*.json in this repo, as of the pilot run), not
against an idealized future shape. Every field name, required/optional
split, and enum value below was checked against the real fixture files
before being written -- run `pytest tests/test_schemas.py` to see them
parse the real artifacts with zero validation errors.

Two deliberate design notes, both flagged in the maturation plan and
repeated here so they aren't lost:

1. `confidence` on DiagnosticRecord is `str`, not an enum. The real
   process_variant_analysis.json artifact stores a full sentence
   ("high confidence in the V4 count itself ... low on the two
   long-resolution variants ...") rather than a single low/medium/high
   token. Forcing this into a Literal would either reject real production
   output or silently truncate it. If the team wants a machine-checkable
   confidence going forward, that's a new field to add (e.g.
   `confidence_label: Literal[...]` alongside the free-text `confidence`),
   not a retrofit of this one.

2. `category` on DiagnosticRecord is `str`, not a Literal drawn from the
   architecture doc's original diagnostic-family list. The real pipeline
   already emits `process_variant_discovery`, a category not in that
   original list -- the taxonomy is evidently still evolving in practice,
   and a strict enum here would have broken on real output that's already
   shipped.

Everything else that a real fixture consistently constrains (direction,
causal_status, disposition, data_quality_status, autonomy_level) IS a
Literal, specifically because every real example observed follows it.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Shared enums / type aliases
# ---------------------------------------------------------------------------

Direction = Literal["higher_is_better", "lower_is_better"]
DataQualityStatus = Literal["HIGH", "MEDIUM", "LOW", "UNUSABLE"]
CausalStatus = Literal["observed", "hypothesis", "supported", "unverified"]
Severity = Literal["low", "medium", "high", "critical"]
Disposition = Literal["PASS", "LOW_CONFIDENCE", "REJECT", "UNVERIFIABLE_NEEDS_HUMAN_REVIEW"]

# "n/a" is included deliberately: it is the literal value the real pipeline
# writes into autonomy_level when ai_fit == NO_AI_RECOMMENDATION. Excluding
# it would break parsing of the one real example we have of that path.
AutonomyLevel = Literal["ASSISTIVE", "HUMAN_IN_LOOP", "BOUNDED_AUTOMATION", "AUTONOMOUS", "n/a"]

NO_AI_RECOMMENDATION = "NO_AI_RECOMMENDATION"


def parse_versioned_metric_id(value: str) -> "tuple[str, Optional[int]]":
    """
    Real fixtures use TWO different conventions for the same metric,
    discovered while wiring the orchestrator's cross-artifact checks:

        MetricContract.metric_id        == "order_straight_through_rate"        (bare, + separate `version: 1` field)
        EvidenceBundle.metric_contract_id == "order_straight_through_rate:1"    (composite name:version)
        BenchmarkRecord.metric_id         == "order_straight_through_rate:1"    (composite name:version)

    Rather than silently loosening a cross-reference check to paper over
    this, parse the composite form explicitly so callers can validate
    BOTH the base name and the version number against MetricContract's
    own fields. If a future MetricContract version 2 exists, an
    EvidenceBundle referencing "order_straight_through_rate:1" should
    NOT be treated as matching it -- that distinction matters and this
    helper preserves it instead of discarding it via a prefix match.

    Returns (base_id, version) -- version is None if no ":<int>" suffix
    is present (e.g. a bare id was passed in).
    """
    if ":" in value:
        base, _, version_str = value.rpartition(":")
        if version_str.isdigit():
            return base, int(version_str)
    return value, None


def compute_query_hash(query: str) -> str:
    """
    Repo convention for EvidenceBundle.query_hash, confirmed empirically
    against artifacts/evidence/order_straight_through_rate_20260918T161600Z.json:

        query_hash == sha256(query_string.encode("utf-8")).hexdigest()

    Centralized here so schemas.py's validator and verifier.py's
    independent re-execution check use exactly the same definition --
    two call sites, one implementation, no risk of them drifting apart.
    """
    return hashlib.sha256(query.encode("utf-8")).hexdigest()


class StrictArtifact(BaseModel):
    """
    Base class for every artifact below. `extra="forbid"` is intentional:
    an unexpected field showing up in production output should fail loudly
    at parse time, not be silently dropped. If a layer's output genuinely
    needs a new field, that's a schema version bump (see MetricContract's
    own `version` field for the pattern), not an implicit schema change.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


# ---------------------------------------------------------------------------
# 1. BusinessFunctionContext  (artifacts/business_context/*.json)
# ---------------------------------------------------------------------------


class BusinessFunctionContext(StrictArtifact):
    business_function: str
    use_case: str
    process_scope: str
    customer_goal: List[str]
    stated_current_state: str
    desired_target: List[str]
    time_horizon: str
    organizational_scope: str
    constraints: List[str] = Field(default_factory=list)
    authorized_sources: List[str]
    unresolved_questions: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 2. MetricContract  (artifacts/metric_contracts/*.json)
# ---------------------------------------------------------------------------


class MetricContract(StrictArtifact):
    metric_id: str
    version: int = Field(ge=1)
    business_process: str
    metric_name: str
    user_goal_text: str
    semantic_definition: str
    direction: Direction
    numerator_definition: str
    denominator_definition: str
    grain: str
    unit: str
    time_window: str
    inclusion_rules: List[str] = Field(default_factory=list)
    exclusion_rules: List[str] = Field(default_factory=list)
    dimensions: List[str] = Field(default_factory=list)

    # Null is a legitimate, common state: "proceed evidence-first, no
    # customer target yet" is a valid MetricContract, not an error.
    target_value: Optional[float] = None
    target_source: str

    source_entities: List[str]
    gold_fields: List[str]
    executable_query_template: str
    expected_result_shape: str
    data_quality_requirements: List[str] = Field(default_factory=list)
    minimum_sample_guidance: str
    framework_references: List[str] = Field(default_factory=list)
    provenance: str
    semantic_model_ref: Optional[str] = None
    verified_query_ref: Optional[str] = None


# ---------------------------------------------------------------------------
# 3. EvidenceBundle  (artifacts/evidence/*.json)
# ---------------------------------------------------------------------------


class EvidenceBundle(StrictArtifact):
    evidence_id: str
    metric_contract_id: str
    observed_value: float
    period: str
    sample_size: int = Field(ge=0)
    distribution_summary: Dict[str, Any] = Field(default_factory=dict)
    trend_summary: str
    segment_results: List[Dict[str, Any]] = Field(default_factory=list)

    # Warehouse object names (e.g. "gold.fct_orders"), not filesystem
    # paths -- deliberately out of scope for verify_provenance's
    # filesystem check; a warehouse-schema check is a different engine.
    source_objects: List[str]

    query: str
    query_hash: str
    execution_timestamp: str
    data_quality_status: DataQualityStatus
    freshness_status: str
    source_coverage: str
    caveats: List[str] = Field(default_factory=list)
    provenance_chain: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_query_hash_integrity(self) -> "EvidenceBundle":
        expected = compute_query_hash(self.query)
        if expected != self.query_hash:
            raise ValueError(
                "query_hash does not match sha256(query) -- the stored SQL "
                f"text and its recorded hash have diverged for evidence_id="
                f"{self.evidence_id!r}. Either the query was edited after "
                "hashing, or this bundle was tampered with. Refusing to "
                "parse rather than silently trusting an unverifiable hash."
            )
        return self


# ---------------------------------------------------------------------------
# 4. DiagnosticRecord  (artifacts/diagnostics/*.json)
# ---------------------------------------------------------------------------


class NotDiagnosableFamily(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: str
    reason: str


class DiagnosticRecord(StrictArtifact):
    diagnostic_id: str
    category: str  # see module docstring note (2) -- deliberately not a Literal
    method: Optional[str] = None
    observation: str
    interpretation: str
    evidence_ids: List[str]
    source_queries: List[str] = Field(default_factory=list)
    affected_process_steps: List[str] = Field(default_factory=list)
    affected_segments: List[str] = Field(default_factory=list)
    severity: Severity
    confidence: str  # see module docstring note (1) -- deliberately not a Literal
    causal_status: CausalStatus
    not_diagnosable_families: Optional[List[NotDiagnosableFamily]] = None


# ---------------------------------------------------------------------------
# 5. AIOpportunityRecord  (artifacts/ai_opportunities/*.json)
# ---------------------------------------------------------------------------


class TaskCharacteristics(BaseModel):
    """
    The 8 dimensions the pilot's single real example scores today.
    extra="allow" here (not "forbid") is deliberate and forward-looking:
    the lead's P2 plan explicitly upgrades L8 from a 1D task-fit score to
    a 3-pillar evaluation (Task Suitability / Data Readiness /
    Organizational Governance). New dimensional scores landing inside
    this sub-object should not break parsing of records written under
    today's 8-dimension scheme. The AIOpportunityRecord's own
    `data_readiness` / `organizational_governance` fields below are the
    proper home for the two new pillars once they exist -- this `allow`
    is a safety margin, not an invitation to keep bolting fields onto
    task_characteristics indefinitely.
    """

    model_config = ConfigDict(extra="allow")

    repeatability: int
    data_availability: int
    determinism: int
    exception_rate: int
    judgment_intensity: int
    error_consequence: int
    workflow_integration: int
    governance_sensitivity: int


class AIOpportunityRecord(StrictArtifact):
    opportunity_id: str
    linked_metric_gaps: List[str] = Field(default_factory=list)
    linked_diagnostics: List[str] = Field(default_factory=list)
    process_step: str
    observed_problem: str
    evidence_ids: List[str]
    task_characteristics: TaskCharacteristics

    # Free text on purpose: the one real example carries the sentinel
    # "NO_AI_RECOMMENDATION" (see NO_AI_RECOMMENDATION constant above),
    # but an affirmative record would carry a descriptive fit statement,
    # not a fixed enum token.
    ai_fit: str

    readiness: str
    risk_profile: str
    autonomy_level: AutonomyLevel
    expected_kpi_impact: str
    dependencies: List[str] = Field(default_factory=list)
    human_control_points: List[str] = Field(default_factory=list)
    recommendation_confidence: str

    # Not present in any current artifact -- reserved for the P2 3-pillar
    # upgrade the lead described. Optional + None-default means today's
    # records parse unchanged; a future L8 can start populating these
    # without a breaking schema change.
    data_readiness: Optional[Dict[str, Any]] = None
    organizational_governance: Optional[Dict[str, Any]] = None

    @property
    def is_ai_recommended(self) -> bool:
        return self.ai_fit != NO_AI_RECOMMENDATION


# ---------------------------------------------------------------------------
# 6. BenchmarkRecord  (artifacts/benchmarks/*.json)
# ---------------------------------------------------------------------------


class BenchmarkRecord(StrictArtifact):
    metric_id: str
    benchmark_source: str
    cohort_definition: str
    cohort_count: int = Field(ge=0)
    cases_per_cohort: int = Field(ge=0)
    direction: Direction
    statistic_used: str
    benchmark_value: Optional[float] = None
    stability: str
    comparability: str
    suppression_reason: Optional[str] = None

    @property
    def is_suppressed(self) -> bool:
        return self.suppression_reason is not None


# ---------------------------------------------------------------------------
# 7. VerificationResult  (artifacts/verification/*.json)
# ---------------------------------------------------------------------------


class EngineResults(BaseModel):
    """
    The 7 engines that run before synthesis exists. narrative_integrity
    is genuinely optional: per the verification-adversarial-review skill,
    it only runs AFTER L11 has produced a FindingDraft, so a
    pre-synthesis VerificationResult (the only kind in this repo's
    fixtures today) will never have it populated.
    """

    model_config = ConfigDict(extra="forbid")

    semantic_check: str
    query_reexecution: str
    arithmetic_check: str
    data_quality_check: str
    benchmark_check: str
    contradiction_check: str
    provenance_check: str
    narrative_integrity: Optional[str] = None


class VerificationResult(StrictArtifact):
    verification_id: str
    checked_records: List[str]
    engine_results: EngineResults
    disposition: Disposition
    retry_count: int = Field(default=0, ge=0)
    notes: str


# ---------------------------------------------------------------------------
# 8. FindingDraft  (artifacts/findings/*.json)
# ---------------------------------------------------------------------------


class FindingDraft(StrictArtifact):
    finding_id: str
    headline: str
    severity: str
    verified_metrics: List[str]
    linked_evidence: List[str]
    diagnosis: List[str] = Field(default_factory=list)
    benchmark_context: str
    ai_opportunity: str
    advisory_match: str
    verification_status: str
    confidence: str
    provenance_chain: List[str]

    @field_validator("provenance_chain")
    @classmethod
    def _must_be_non_empty(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError(
                "FindingDraft.provenance_chain is empty -- a finding with "
                "no provenance chain cannot be traced back to source and "
                "must never be constructed, let alone released."
            )
        return v
