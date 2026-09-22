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

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple

from engine.schemas import (
    AIOpportunityRecord,
    BenchmarkRecord,
    BusinessFunctionContext,
    DiagnosticRecord,
    EvidenceBundle,
    FindingDraft,
    MetricContract,
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
    PipelineState.TARGETED_RETRY: (PipelineState.VERIFICATION,),
    PipelineState.SYNTHESIZED: (PipelineState.FINDING_RELEASED,),
    # HUMAN_REVIEW and FINDING_RELEASED are terminal for this module.
    PipelineState.HUMAN_REVIEW: (),
    PipelineState.FINDING_RELEASED: (),
}

MAX_VERIFICATION_RETRIES = 2


class InvalidTransitionError(Exception):
    """Raised when code tries to move the pipeline through a transition
    that isn't in _VALID_TRANSITIONS. This is the state machine actually
    refusing something, not a lint warning."""


class GateNotSatisfiedError(Exception):
    """Raised when a layer is recorded out of order, or when synthesis
    is attempted without a passing verification gate."""


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
        if self.state not in (PipelineState.BENCHMARKED, PipelineState.TARGETED_RETRY):
            raise GateNotSatisfiedError(f"cannot record verification from state {self.state}")

        # BENCHMARKED -> VERIFICATION is a direct transition; a retry loop
        # re-enters VERIFICATION from TARGETED_RETRY (see _VALID_TRANSITIONS).
        if self.state == PipelineState.BENCHMARKED:
            self.transition(PipelineState.VERIFICATION)
        else:
            self.transition(PipelineState.VERIFICATION)

        self._verification = result

        if result.disposition in ("PASS", "LOW_CONFIDENCE"):
            return  # caller may now proceed to record_finding

        if result.disposition == "REJECT":
            self._verification_retry_count += 1
            if self._verification_retry_count <= MAX_VERIFICATION_RETRIES:
                self.transition(PipelineState.TARGETED_RETRY)
            else:
                self.transition(PipelineState.HUMAN_REVIEW)
            return

        if result.disposition == "UNVERIFIABLE_NEEDS_HUMAN_REVIEW":
            self.transition(PipelineState.HUMAN_REVIEW)
            return

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
            "transitions": [
                {"from": t.from_state.value, "to": t.to_state.value, "at": t.at.isoformat()}
                for t in self._transition_log
            ],
        }
