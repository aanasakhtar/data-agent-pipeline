"""
engine/orchestrator.py
=======================
State machine + payload isolation for the L4-L11 reasoning chain.

What this module IS: real, enforced infrastructure. The state machine
rejects illegal transitions (raises, doesn't just log). The isolation
payloads are frozen dataclasses containing ONLY the fields a given layer
is allowed to see -- a test can assert `hasattr(payload, "query") is
False` on the Synthesis payload and get a real answer, not a matter of
prompt-reading discipline.

What this module IS NOT: it does not call an LLM. Building L4-L11's
actual reasoning (turning a MetricContract into an EvidenceBundle, an
EvidenceBundle into DiagnosticRecords, etc.) still requires an agent call
per layer -- that's P1 work, sequenced after this skeleton is solid. This
file's job is to make sure that whatever eventually calls those agents
can only hand them the fields they're supposed to see, and can't silently
skip verification or release an unverified finding.

Layer sequence and gating, from the architecture doc's state machine
(only the states this module actually implements; NEEDS_INPUT and
DATA_REPAIR/SUPPRESS are modeled but their human-in-the-loop UX is
explicitly out of scope here -- see maturation plan F-item on this):

    CREATED
      -> INTENT_RESOLVED          (record_business_context)
      -> METRICS_RESOLVED         (record_metric_contract)
      -> CURRENT_STATE_MEASURED   (record_evidence)
      -> OPERATIONALLY_DIAGNOSED  (record_diagnostics)
      -> AI_OPPORTUNITIES_ASSESSED(record_ai_opportunity)
      -> BENCHMARKED              (record_benchmark)
      -> VERIFICATION             (record_verification)
          -- PASS/LOW_CONFIDENCE  -> may proceed to synthesis
          -- REJECT, retry<2      -> TARGETED_RETRY -> back to VERIFICATION
          -- REJECT, retry>=2     -> HUMAN_REVIEW (terminal for this module)
          -- UNVERIFIABLE_...     -> HUMAN_REVIEW (terminal for this module)
      -> SYNTHESIZED -> FINDING_RELEASED   (record_finding)
"""

from __future__ import annotations

import hashlib
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from engine.gates import evidence_quality_gate, metric_contract_gate
from engine.schemas import (
    AIOpportunityRecord,
    BenchmarkRecord,
    BusinessFunctionContext,
    DiagnosticRecord,
    EvidenceBundle,
    FindingDraft,
    MetricContract,
    RunManifest,
    VerificationResult,
    parse_versioned_metric_id,
)


class PipelineState(str, Enum):
    CREATED = "CREATED"
    INTENT_RESOLVED = "INTENT_RESOLVED"
    METRICS_RESOLVED = "METRICS_RESOLVED"
    CURRENT_STATE_MEASURED = "CURRENT_STATE_MEASURED"
    OPERATIONALLY_DIAGNOSED = "OPERATIONALLY_DIAGNOSED"
    AI_OPPORTUNITIES_ASSESSED = "AI_OPPORTUNITIES_ASSESSED"
    BENCHMARKED = "BENCHMARKED"
    VERIFICATION = "VERIFICATION"
    TARGETED_RETRY = "TARGETED_RETRY"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    SYNTHESIZED = "SYNTHESIZED"
    FINDING_RELEASED = "FINDING_RELEASED"


class RetryTarget(str, Enum):
    """
    Blueprint section 17: retry must be dependency-aware, not a blind
    restart of the whole pipeline. Each value names which layer's
    artifact gets invalidated (and therefore regenerated) -- everything
    upstream of that layer is left untouched and reusable.
    """

    RETRY_METRIC_CONTRACT = "RETRY_METRIC_CONTRACT"  # L5 was wrong (semantic_check)
    RETRY_EVIDENCE = "RETRY_EVIDENCE"                 # L6 was wrong (query/arithmetic)
    RETRY_DIAGNOSIS = "RETRY_DIAGNOSIS"               # L7 was wrong (contradiction)
    RETRY_AI_OPPORTUNITY = "RETRY_AI_OPPORTUNITY"     # L8 was wrong
    RETRY_BENCHMARK = "RETRY_BENCHMARK"               # L9 was wrong
    RETRY_VERIFICATION_ONLY = "RETRY_VERIFICATION_ONLY"  # e.g. synthesis-only issue; nothing upstream needs to change


# Where TARGETED_RETRY routes back TO, per target -- this table plus
# classify_retry_target() below is the entire "dependency graph" from
# the blueprint's section 17 diagram, expressed as code instead of a
# picture.
_RETRY_TARGET_STATE: Dict[RetryTarget, "PipelineState"] = {}  # populated after PipelineState is fully defined below


def classify_retry_target(result: VerificationResult) -> RetryTarget:
    """
    Reads which engine(s) failed inside a REJECT VerificationResult and
    decides the MINIMAL invalidation needed -- e.g. a query-reexecution
    or arithmetic failure means L6's EvidenceBundle was wrong, so only
    L6 and everything downstream of it needs to be regenerated; L4/L5
    (BusinessFunctionContext, MetricContract) remain valid and are not
    touched. Conservative default (RETRY_EVIDENCE) when a failure can't
    be attributed to a specific engine -- regenerating evidence is the
    safest fallback since everything else depends on it anyway.
    """
    er = result.engine_results

    def _failed(status: Optional[str]) -> bool:
        return bool(status) and status.startswith("FAIL")

    if _failed(er.query_reexecution) or _failed(er.arithmetic_check):
        return RetryTarget.RETRY_EVIDENCE
    if _failed(er.semantic_check):
        return RetryTarget.RETRY_METRIC_CONTRACT
    if _failed(er.contradiction_check):
        return RetryTarget.RETRY_DIAGNOSIS
    if _failed(er.benchmark_check):
        return RetryTarget.RETRY_BENCHMARK
    if _failed(er.narrative_integrity):
        return RetryTarget.RETRY_VERIFICATION_ONLY
    return RetryTarget.RETRY_EVIDENCE


# Explicit allow-list of legal transitions. Anything not listed here is
# refused by `transition()` -- this is the actual enforcement mechanism,
# not the docstring above.
_VALID_TRANSITIONS: Dict[PipelineState, Tuple[PipelineState, ...]] = {
    PipelineState.CREATED: (PipelineState.INTENT_RESOLVED,),
    PipelineState.INTENT_RESOLVED: (PipelineState.METRICS_RESOLVED,),
    PipelineState.METRICS_RESOLVED: (PipelineState.CURRENT_STATE_MEASURED,),
    PipelineState.CURRENT_STATE_MEASURED: (PipelineState.OPERATIONALLY_DIAGNOSED,),
    PipelineState.OPERATIONALLY_DIAGNOSED: (PipelineState.AI_OPPORTUNITIES_ASSESSED,),
    PipelineState.AI_OPPORTUNITIES_ASSESSED: (PipelineState.BENCHMARKED,),
    PipelineState.BENCHMARKED: (PipelineState.VERIFICATION,),
    PipelineState.VERIFICATION: (
        PipelineState.SYNTHESIZED,
        PipelineState.TARGETED_RETRY,
        PipelineState.HUMAN_REVIEW,
    ),
    # A retry can route back to ANY earlier stage, depending on which
    # layer's artifact was invalidated -- see RetryTarget / classify_retry_target.
    PipelineState.TARGETED_RETRY: (
        PipelineState.INTENT_RESOLVED,
        PipelineState.METRICS_RESOLVED,
        PipelineState.CURRENT_STATE_MEASURED,
        PipelineState.OPERATIONALLY_DIAGNOSED,
        PipelineState.AI_OPPORTUNITIES_ASSESSED,
        PipelineState.BENCHMARKED,
    ),
    PipelineState.SYNTHESIZED: (PipelineState.FINDING_RELEASED,),
    # HUMAN_REVIEW and FINDING_RELEASED are terminal for this module.
    PipelineState.HUMAN_REVIEW: (),
    PipelineState.FINDING_RELEASED: (),
}

_RETRY_TARGET_STATE.update(
    {
        RetryTarget.RETRY_METRIC_CONTRACT: PipelineState.INTENT_RESOLVED,
        RetryTarget.RETRY_EVIDENCE: PipelineState.METRICS_RESOLVED,
        RetryTarget.RETRY_DIAGNOSIS: PipelineState.CURRENT_STATE_MEASURED,
        RetryTarget.RETRY_AI_OPPORTUNITY: PipelineState.OPERATIONALLY_DIAGNOSED,
        RetryTarget.RETRY_BENCHMARK: PipelineState.AI_OPPORTUNITIES_ASSESSED,
        RetryTarget.RETRY_VERIFICATION_ONLY: PipelineState.BENCHMARKED,
    }
)

MAX_VERIFICATION_RETRIES = 2


class InvalidTransitionError(Exception):
    """Raised when code tries to move the pipeline through a transition
    that isn't in _VALID_TRANSITIONS. This is the state machine actually
    refusing something, not a lint warning."""


class GateNotSatisfiedError(Exception):
    """Raised when a layer is recorded out of order, or when synthesis
    is attempted without a passing verification gate."""


class MetricNotResolvableError(GateNotSatisfiedError):
    """Raised when a MetricContract's resolution_status (or basic
    well-formedness -- see engine.gates.metric_contract_gate) blocks it
    from proceeding to evidence measurement. The contract is NOT stored
    and state does NOT advance -- caller must supply a corrected or
    resolved contract before retrying record_metric_contract."""


class EvidenceNotUsableError(GateNotSatisfiedError):
    """Raised when an EvidenceBundle fails the pre-diagnosis quality gate
    (UNUSABLE data quality, or sample size below the contract's own
    stated minimum). The evidence is NOT stored and state does NOT
    advance."""


# ---------------------------------------------------------------------------
# Isolation payloads
# ---------------------------------------------------------------------------
# Each of these is the ENTIRE input a given layer receives. If a field
# isn't listed here, that layer structurally cannot see it -- there is no
# ambient access to the orchestrator's full artifact store from inside a
# layer call built this way.


@dataclass(frozen=True)
class EvidenceLayerPayload:
    """L6 input. Deliberately just the MetricContract -- no
    BusinessFunctionContext, no financial data of any kind."""

    metric_contract: MetricContract


@dataclass(frozen=True)
class DiagnosisLayerPayload:
    """L7 input. The measured evidence only -- no target/goal framing
    beyond what's already inside the EvidenceBundle's own caveats, and
    no financial data."""

    evidence: EvidenceBundle


@dataclass(frozen=True)
class AIOpportunityLayerPayload:
    """L8 input. Evidence + diagnostics, read-only (frozen). No ability
    to rewrite either -- an L8 call can only produce a NEW
    AIOpportunityRecord, never mutate its inputs."""

    evidence: EvidenceBundle
    diagnostics: Tuple[DiagnosticRecord, ...]


@dataclass(frozen=True)
class BenchmarkLayerPayload:
    """L9 input. Evidence only -- no financial data, matching the
    architecture's "benchmark agent never sees roleRoster" invariant."""

    evidence: EvidenceBundle


@dataclass(frozen=True)
class VerifierLayerPayload:
    """
    L10 input. Everything needed to independently re-derive, nothing
    that constitutes "the producing agent's reasoning trace" -- these
    artifacts already ARE the structured final outputs (there is no
    separate scratchpad field to withhold), so passing the full typed
    objects here does not leak chain-of-thought, only the same
    structured claims a human reviewer would also need to check them.
    """

    evidence: EvidenceBundle
    diagnostics: Tuple[DiagnosticRecord, ...]
    ai_opportunity: AIOpportunityRecord
    benchmark: BenchmarkRecord
    retry_count: int


@dataclass(frozen=True)
class SynthesisLayerPayload:
    """
    L11 input. This is the structural enforcement of "no source-data
    access, cannot alter a verified number": notice `query`,
    `query_hash`, and `source_objects` from EvidenceBundle are NOT
    present anywhere below. Synthesis receives the verified VALUE, not
    the bundle that could be used to recompute a different one.
    """

    verified_metric_id: str
    verified_metric_value: float
    metric_unit: str
    diagnostics: Tuple[DiagnosticRecord, ...]
    ai_opportunity: AIOpportunityRecord
    benchmark: BenchmarkRecord
    verification_disposition: str
    verification_notes: str


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


@dataclass
class TransitionLogEntry:
    from_state: PipelineState
    to_state: PipelineState
    at: datetime


class PipelineOrchestrator:
    """
    Owns the run's identity, state, and artifact store. Layers are
    recorded one at a time via `record_*` methods; each method validates
    ordering, stores the (already Pydantic-validated, by construction)
    artifact, and transitions state. `build_*_payload` methods are the
    only way to get data OUT for a layer call, and they return the
    narrow dataclasses above -- never `self` or the internal store.
    """

    def __init__(
        self,
        customer_id: str,
        business_function: str,
        run_id: Optional[str] = None,
        pinned_timestamp: Optional[datetime] = None,
    ) -> None:
        self.run_id = run_id or str(uuid.uuid4())
        self.customer_id = customer_id
        self.business_function = business_function
        self.created_at = pinned_timestamp or datetime.now(timezone.utc)
        self.state = PipelineState.CREATED

        self._transition_log: List[TransitionLogEntry] = []
        self._verification_retry_count = 0
        self._last_retry_target: Optional[RetryTarget] = None

        self._business_context: Optional[BusinessFunctionContext] = None
        self._metric_contract: Optional[MetricContract] = None
        self._evidence: Optional[EvidenceBundle] = None
        self._diagnostics: Tuple[DiagnosticRecord, ...] = ()
        self._ai_opportunity: Optional[AIOpportunityRecord] = None
        self._benchmark: Optional[BenchmarkRecord] = None
        self._verification: Optional[VerificationResult] = None
        self._finding: Optional[FindingDraft] = None

    # -- state machine primitive -------------------------------------------------

    def transition(self, new_state: PipelineState) -> None:
        allowed = _VALID_TRANSITIONS.get(self.state, ())
        if new_state not in allowed:
            raise InvalidTransitionError(
                f"run {self.run_id}: cannot transition {self.state.value} -> "
                f"{new_state.value}. Allowed from {self.state.value}: "
                f"{[s.value for s in allowed] or '(terminal state)'}"
            )
        self._transition_log.append(
            TransitionLogEntry(self.state, new_state, datetime.now(timezone.utc))
        )
        self.state = new_state

    @property
    def transition_log(self) -> List[TransitionLogEntry]:
        return list(self._transition_log)

    # -- record_* : validate ordering, store, advance state ----------------------

    def record_business_context(self, ctx: BusinessFunctionContext) -> None:
        if self.state != PipelineState.CREATED:
            raise GateNotSatisfiedError(f"cannot record business context from state {self.state}")
        self._business_context = ctx
        self.transition(PipelineState.INTENT_RESOLVED)

    def record_metric_contract(self, contract: MetricContract) -> None:
        if self.state != PipelineState.INTENT_RESOLVED:
            raise GateNotSatisfiedError(f"cannot record metric contract from state {self.state}")
        gate_reason = metric_contract_gate(contract)
        if gate_reason is not None:
            # Deliberately does NOT store the contract or advance state --
            # caller must supply a corrected/resolved contract and call
            # this again from the same state.
            raise MetricNotResolvableError(
                f"MetricContract {contract.metric_id!r} failed the pre-evidence gate: {gate_reason}"
            )
        self._metric_contract = contract
        self.transition(PipelineState.METRICS_RESOLVED)

    def record_evidence(self, evidence: EvidenceBundle) -> None:
        if self.state != PipelineState.METRICS_RESOLVED:
            raise GateNotSatisfiedError(f"cannot record evidence from state {self.state}")
        if self._metric_contract is None:
            raise GateNotSatisfiedError("no metric contract on file -- cannot accept evidence")
        # evidence.metric_contract_id may be bare ("foo") or composite
        # ("foo:1") -- see parse_versioned_metric_id docstring for why this
        # is parsed rather than compared as a raw string.
        ev_base, ev_version = parse_versioned_metric_id(evidence.metric_contract_id)
        if ev_base != self._metric_contract.metric_id:
            raise GateNotSatisfiedError(
                f"evidence.metric_contract_id={evidence.metric_contract_id!r} (base="
                f"{ev_base!r}) does not match the metric contract on file "
                f"({self._metric_contract.metric_id!r})"
            )
        if ev_version is not None and ev_version != self._metric_contract.version:
            raise GateNotSatisfiedError(
                f"evidence.metric_contract_id={evidence.metric_contract_id!r} references "
                f"version {ev_version}, but the metric contract on file is version "
                f"{self._metric_contract.version}"
            )
        gate_reason = evidence_quality_gate(evidence, self._metric_contract)
        if gate_reason is not None:
            raise EvidenceNotUsableError(
                f"EvidenceBundle {evidence.evidence_id!r} failed the pre-diagnosis gate: {gate_reason}"
            )
        self._evidence = evidence
        self.transition(PipelineState.CURRENT_STATE_MEASURED)

    def record_diagnostics(self, diagnostics: List[DiagnosticRecord]) -> None:
        if self.state != PipelineState.CURRENT_STATE_MEASURED:
            raise GateNotSatisfiedError(f"cannot record diagnostics from state {self.state}")
        self._diagnostics = tuple(diagnostics)
        self.transition(PipelineState.OPERATIONALLY_DIAGNOSED)

    def record_ai_opportunity(self, opportunity: AIOpportunityRecord) -> None:
        if self.state != PipelineState.OPERATIONALLY_DIAGNOSED:
            raise GateNotSatisfiedError(f"cannot record AI opportunity from state {self.state}")
        self._ai_opportunity = opportunity
        self.transition(PipelineState.AI_OPPORTUNITIES_ASSESSED)

    def record_benchmark(self, benchmark: BenchmarkRecord) -> None:
        if self.state != PipelineState.AI_OPPORTUNITIES_ASSESSED:
            raise GateNotSatisfiedError(f"cannot record benchmark from state {self.state}")
        self._benchmark = benchmark
        self.transition(PipelineState.BENCHMARKED)

    def record_verification(self, result: VerificationResult) -> None:
        if self.state != PipelineState.BENCHMARKED:
            raise GateNotSatisfiedError(f"cannot record verification from state {self.state}")

        self.transition(PipelineState.VERIFICATION)
        self._verification = result
        self._last_retry_target = None

        if result.disposition in ("PASS", "LOW_CONFIDENCE"):
            return  # caller may now proceed to record_finding

        if result.disposition == "REJECT":
            self._verification_retry_count += 1
            if self._verification_retry_count <= MAX_VERIFICATION_RETRIES:
                target = classify_retry_target(result)
                self._invalidate_and_route(target)
            else:
                self.transition(PipelineState.HUMAN_REVIEW)
            return

        if result.disposition == "UNVERIFIABLE_NEEDS_HUMAN_REVIEW":
            self.transition(PipelineState.HUMAN_REVIEW)
            return

    def _invalidate_and_route(self, target: RetryTarget) -> None:
        """
        The actual dependency-aware invalidation: clears exactly the
        artifacts that depend on the layer identified as wrong, leaves
        everything upstream untouched, and routes the state machine back
        to the point where regeneration should resume. Logged as its own
        TARGETED_RETRY transition first (so the transition log shows a
        retry happened, and to what target) before landing on the resume
        state.
        """
        self.transition(PipelineState.TARGETED_RETRY)
        self._last_retry_target = target

        if target == RetryTarget.RETRY_METRIC_CONTRACT:
            self._metric_contract = None
            self._evidence = None
            self._diagnostics = ()
            self._ai_opportunity = None
            self._benchmark = None
        elif target == RetryTarget.RETRY_EVIDENCE:
            self._evidence = None
            self._diagnostics = ()
            self._ai_opportunity = None
            self._benchmark = None
        elif target == RetryTarget.RETRY_DIAGNOSIS:
            self._diagnostics = ()
            self._ai_opportunity = None
            self._benchmark = None
        elif target == RetryTarget.RETRY_AI_OPPORTUNITY:
            self._ai_opportunity = None
            self._benchmark = None
        elif target == RetryTarget.RETRY_BENCHMARK:
            self._benchmark = None
        # RETRY_VERIFICATION_ONLY invalidates nothing upstream -- only
        # self._verification, which record_verification already
        # overwrote before calling this method.

        self.transition(_RETRY_TARGET_STATE[target])

    def record_finding(self, finding: FindingDraft) -> None:
        if self.state != PipelineState.VERIFICATION:
            raise GateNotSatisfiedError(
                f"cannot synthesize a finding from state {self.state} -- "
                "verification gate has not been passed"
            )
        if self._verification is None or self._verification.disposition not in (
            "PASS",
            "LOW_CONFIDENCE",
        ):
            raise GateNotSatisfiedError(
                "refusing to release a finding: verification disposition is "
                f"{self._verification.disposition if self._verification else 'MISSING'}, "
                "not PASS or LOW_CONFIDENCE"
            )
        self._finding = finding
        self.transition(PipelineState.SYNTHESIZED)
        self.transition(PipelineState.FINDING_RELEASED)

    # -- build_*_payload : the actual isolation enforcement -----------------------

    def build_evidence_payload(self) -> EvidenceLayerPayload:
        if self._metric_contract is None:
            raise GateNotSatisfiedError("no metric contract recorded yet")
        return EvidenceLayerPayload(metric_contract=self._metric_contract)

    def build_diagnosis_payload(self) -> DiagnosisLayerPayload:
        if self._evidence is None:
            raise GateNotSatisfiedError("no evidence recorded yet")
        return DiagnosisLayerPayload(evidence=self._evidence)

    def build_ai_opportunity_payload(self) -> AIOpportunityLayerPayload:
        if self._evidence is None:
            raise GateNotSatisfiedError("no evidence recorded yet")
        return AIOpportunityLayerPayload(evidence=self._evidence, diagnostics=self._diagnostics)

    def build_benchmark_payload(self) -> BenchmarkLayerPayload:
        if self._evidence is None:
            raise GateNotSatisfiedError("no evidence recorded yet")
        return BenchmarkLayerPayload(evidence=self._evidence)

    def build_verifier_payload(self) -> VerifierLayerPayload:
        if not all([self._evidence, self._ai_opportunity, self._benchmark]):
            raise GateNotSatisfiedError("cannot build verifier payload -- upstream layers incomplete")
        return VerifierLayerPayload(
            evidence=self._evidence,  # type: ignore[arg-type]
            diagnostics=self._diagnostics,
            ai_opportunity=self._ai_opportunity,  # type: ignore[arg-type]
            benchmark=self._benchmark,  # type: ignore[arg-type]
            retry_count=self._verification_retry_count,
        )

    def build_synthesis_payload(self) -> SynthesisLayerPayload:
        if self._verification is None or self._verification.disposition not in (
            "PASS",
            "LOW_CONFIDENCE",
        ):
            raise GateNotSatisfiedError(
                "cannot build synthesis payload -- verification has not passed"
            )
        assert self._evidence is not None
        assert self._ai_opportunity is not None
        assert self._benchmark is not None
        return SynthesisLayerPayload(
            verified_metric_id=self._evidence.metric_contract_id,
            verified_metric_value=self._evidence.observed_value,
            metric_unit=self._metric_contract.unit if self._metric_contract else "",
            diagnostics=self._diagnostics,
            ai_opportunity=self._ai_opportunity,
            benchmark=self._benchmark,
            verification_disposition=self._verification.disposition,
            verification_notes=self._verification.notes,
        )

    # -- introspection --------------------------------------------------------

    def summary(self) -> Dict[str, object]:
        return {
            "run_id": self.run_id,
            "customer_id": self.customer_id,
            "business_function": self.business_function,
            "created_at": self.created_at.isoformat(),
            "state": self.state.value,
            "verification_retry_count": self._verification_retry_count,
            "last_retry_target": self._last_retry_target.value if self._last_retry_target else None,
            "transitions": [
                {"from": t.from_state.value, "to": t.to_state.value, "at": t.at.isoformat()}
                for t in self._transition_log
            ],
        }

    def content_fingerprint(self) -> str:
        """
        Hash of the run's material artifact IDs and values (not
        timestamps or run_id). Two independently constructed
        orchestrator runs fed the IDENTICAL fixtures should produce the
        IDENTICAL fingerprint -- this is the testable core of
        "reproducibility" at this layer.

        Important scope limit, stated plainly: this proves the
        deterministic parts of the pipeline (schema validation, state
        machine, artifact linkage) are themselves deterministic. It does
        NOT prove an LLM would generate byte-identical prose twice --
        it wouldn't, and per the blueprint's own reproducibility
        section, that's not actually required for reproducibility to be
        meaningful; what must reproduce is the VERIFIED NUMBER, not the
        sentence describing it.
        """
        parts = [
            self._business_context.business_function if self._business_context else "",
            self._metric_contract.metric_id if self._metric_contract else "",
            str(self._metric_contract.version) if self._metric_contract else "",
            self._evidence.evidence_id if self._evidence else "",
            repr(self._evidence.observed_value) if self._evidence else "",
            ",".join(sorted(d.diagnostic_id for d in self._diagnostics)),
            self._ai_opportunity.opportunity_id if self._ai_opportunity else "",
            self._benchmark.metric_id if self._benchmark else "",
            self._verification.disposition if self._verification else "",
            self._finding.finding_id if self._finding else "",
        ]
        canonical = "|".join(parts)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def build_run_manifest(
        self,
        *,
        repo_root: Path = Path("."),
        artifact_root: Optional[str] = None,
        model_provider: Optional[str] = None,
        model_version: Optional[str] = None,
    ) -> RunManifest:
        """
        Assembles a RunManifest for this run. code_commit_sha and
        dbt_manifest_hash are captured best-effort and left None (never
        fabricated) when unavailable -- e.g. running outside a git
        checkout, or before `dbt build` has produced a target/manifest.json.
        """
        return RunManifest(
            run_id=self.run_id,
            customer_id=self.customer_id,
            business_function=self.business_function,
            created_at=self.created_at.isoformat(),
            source_snapshot_ids=list(self._evidence.source_snapshot_ids) if self._evidence else [],
            code_commit_sha=_get_git_commit_sha(repo_root),
            dbt_manifest_hash=_get_dbt_manifest_hash(repo_root),
            model_provider=model_provider,
            model_version=model_version,
            configuration_hash=self.content_fingerprint(),
            artifact_root=artifact_root,
            status=self.state.value,
        )


def _get_git_commit_sha(repo_root: Path) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _get_dbt_manifest_hash(repo_root: Path) -> Optional[str]:
    manifest_path = repo_root / "dbt" / "customer_platform" / "target" / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        return hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    except OSError:
        return None
