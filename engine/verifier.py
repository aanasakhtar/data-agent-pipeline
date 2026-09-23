"""
engine/verifier.py
===================
Pure Python / DuckDB implementation of the deterministic half of Layer 10.

This is deliberately NOT the whole verifier. Per the maturation plan, L10
splits into:

  - Deterministic engines (this file): query re-execution, arithmetic,
    provenance. No LLM, no ambiguity -- either the number reproduces or
    it doesn't. These run first, cheaply, and catch the failure mode that
    matters most: a citation that was never actually re-checked.

  - Adversarial-review engines (semantic conformance, contradiction,
    narrative integrity): these need a model call, and belong in a
    SEPARATE module once built, given a fresh context containing only
    the record under test and the source artifacts -- never the
    producing agent's reasoning trace, and never the expected value.
    Not implemented here; see docs/deep-research... and the maturation
    plan for why conflating the two halves into one "verifier agent"
    is the open risk in the 11-layer design.

Independence discipline that's actually enforced here, not just claimed:

  - verify_query_reexecution opens its OWN duckdb connection, in
    read-only mode, and only ever calls duckdb.connect(..., read_only=True)
    -- it cannot be the same connection/session the evidence-producing
    layer used, and it cannot write.
  - It re-derives the metric value from the SQL text alone. It is not
    told what the "expected" observed_value is until AFTER it has
    computed its own answer; the comparison happens last, not first.
    (This is the deterministic-code equivalent of a golden test, which
    is legitimate -- the failure mode this whole module exists to avoid
    is an LLM agent that has already READ the expected answer before
    reasoning about whether it holds up. A diff performed by code after
    an independent computation is not that failure mode.)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import duckdb

from engine.schemas import (
    EvidenceBundle,
    EngineResults,
    VerificationResult,
    compute_query_hash,
)

# Real artifacts round observed_value to 4 decimal places (see
# registry/verified_queries/*.yml). Recomputed values are compared at the
# same precision, not to full float equality.
DEFAULT_TOLERANCE = 1e-4

# Fields that, across the 8 artifact types, hold IDs referencing another
# artifact (by declared id field, or by filename stem -- BenchmarkRecord
# has no internal id field, so its only handle is its filename).
_ID_FIELD_CANDIDATES = (
    "evidence_id",
    "diagnostic_id",
    "opportunity_id",
    "metric_contract_id",
    "verification_id",
    "finding_id",
)

_PATH_LIKE_EXTENSIONS = (".json", ".yml", ".yaml", ".sql", ".md")


@dataclass
class EngineCheckResult:
    """Uniform result shape returned by every check function in this module."""

    engine: str
    passed: bool
    detail: str
    computed: Optional[Any] = None
    expected: Optional[Any] = None
    sub_results: List["EngineCheckResult"] = field(default_factory=list)

    def to_status_string(self) -> str:
        """Collapse to the short PASS/FAIL string the artifact schema stores."""
        return f"{'PASS' if self.passed else 'FAIL'} -- {self.detail}"


class VerificationError(Exception):
    """Raised for operational failures (bad path, bad SQL) -- distinct from
    a normal FAIL result, which means the check ran fine and found a problem."""


# ---------------------------------------------------------------------------
# 1. Query re-execution
# ---------------------------------------------------------------------------


def verify_query_reexecution(evidence_bundle: EvidenceBundle, db_path: str) -> EngineCheckResult:
    """
    Opens an independent, read-only DuckDB connection, executes the query
    recorded on the EvidenceBundle, and checks:

      (a) the query text hashes to the recorded query_hash (confirms the
          SQL wasn't altered after being hashed -- this duplicates the
          Pydantic-level check in schemas.py deliberately, as defense in
          depth: schemas.py guards data AT REST, this guards it again
          at THE MOMENT OF RE-VERIFICATION, in case the object was
          constructed some other way that bypassed validation)
      (b) the query actually executes against the given warehouse
      (c) the recomputed metric value matches observed_value within
          DEFAULT_TOLERANCE

    Convention note (not fully solved by the current schema): the query
    returns multiple columns (e.g. completed_orders, no_ticket_orders,
    straight_through_rate), and there is no field anywhere that says
    which column IS "the" metric value. Every query in
    registry/verified_queries/*.yml puts the rate/target metric last, so
    this function takes the LAST column of the single returned row by
    convention. Recommendation: add an explicit `result_value_column:
    str` field to MetricContract so this stops being a convention and
    becomes a declared contract -- flagging here rather than silently
    encoding a fragile assumption.
    """
    if not os.path.exists(db_path):
        raise VerificationError(f"database not found at {db_path!r}")

    hash_ok = compute_query_hash(evidence_bundle.query) == evidence_bundle.query_hash

    con = duckdb.connect(db_path, read_only=True)
    try:
        try:
            rows = con.execute(evidence_bundle.query).fetchall()
            col_names = [d[0] for d in con.description] if con.description else []
        except Exception as exc:  # noqa: BLE001 -- surfacing any SQL error as a FAIL is correct here
            return EngineCheckResult(
                engine="query_reexecution",
                passed=False,
                detail=f"query failed to execute against {db_path}: {exc}",
            )
    finally:
        con.close()

    if len(rows) != 1:
        return EngineCheckResult(
            engine="query_reexecution",
            passed=False,
            detail=f"expected exactly 1 row, got {len(rows)}",
            computed=rows,
        )

    row = rows[0]
    recomputed_value = row[-1]  # last column, by convention -- see docstring

    if not hash_ok:
        return EngineCheckResult(
            engine="query_reexecution",
            passed=False,
            detail=(
                "query_hash does not match sha256(query) -- refusing to trust "
                "the re-execution result even though it ran, because the "
                "recorded query text and its hash have diverged"
            ),
            computed=recomputed_value,
            expected=evidence_bundle.observed_value,
        )

    diff = abs(float(recomputed_value) - float(evidence_bundle.observed_value))
    passed = diff <= DEFAULT_TOLERANCE

    return EngineCheckResult(
        engine="query_reexecution",
        passed=passed,
        detail=(
            f"recomputed {col_names[-1] if col_names else 'value'}="
            f"{recomputed_value} vs recorded observed_value="
            f"{evidence_bundle.observed_value} (diff={diff:.6f}, "
            f"tolerance={DEFAULT_TOLERANCE})"
            if passed
            else (
                f"MISMATCH: recomputed {col_names[-1] if col_names else 'value'}="
                f"{recomputed_value} vs recorded observed_value="
                f"{evidence_bundle.observed_value} (diff={diff:.6f} exceeds "
                f"tolerance={DEFAULT_TOLERANCE})"
            )
        ),
        computed=recomputed_value,
        expected=evidence_bundle.observed_value,
    )


# ---------------------------------------------------------------------------
# 2. Arithmetic re-check
# ---------------------------------------------------------------------------


def verify_arithmetic(evidence_bundle: EvidenceBundle) -> EngineCheckResult:
    """
    Recomputes the overall observed_value FROM THE EVIDENCE BUNDLE'S OWN
    STORED SEGMENT DATA, independent of any database access. This is
    intentionally a different independence axis than
    verify_query_reexecution: that check asks "does the SQL still
    reproduce this against the warehouse"; this one asks "is the
    top-line number even internally consistent with the segment
    breakdown recorded in the same bundle."

    Honest limitation, worth fixing in a future schema version: no
    current EvidenceBundle stores an explicit top-level numerator (e.g.
    "873 of 965"), only observed_value (0.9047) and sample_size (965).
    Segment-level dicts DO carry per-segment counts and rates, so this
    function:

      1. Hard-checks that per-segment case counts sum to sample_size
         (exact -- no rounding involved, so this either holds or it
         doesn't).
      2. Soft-checks that a weighted reconstruction of the numerator
         from (segment_rate * segment_count), rounded per segment,
         reconciles with observed_value * sample_size within a small
         integer tolerance -- soft because segment rates are themselves
         already rounded to 4dp, so this is a reconstruction, not an
         exact derivation.

    Recommendation flagged for the schema: add explicit
    `numerator_value` / `denominator_value` fields to EvidenceBundle so
    check (2) can become exact instead of reconstructed.
    """
    segments = evidence_bundle.segment_results
    if not segments:
        return EngineCheckResult(
            engine="arithmetic_check",
            passed=True,
            detail="no segment_results present -- nothing to cross-check, not a failure",
        )

    count_keys = [k for k in segments[0].keys() if "count" in k.lower() or "orders" in k.lower()]
    rate_keys = [k for k in segments[0].keys() if "rate" in k.lower()]

    if not count_keys or not rate_keys:
        return EngineCheckResult(
            engine="arithmetic_check",
            passed=True,
            detail=(
                "segment_results present but no recognizable count/rate "
                f"keys found (saw keys: {list(segments[0].keys())}) -- "
                "skipping cross-check rather than guessing field names"
            ),
        )

    count_key, rate_key = count_keys[0], rate_keys[0]

    try:
        segment_counts = [int(s[count_key]) for s in segments]
        segment_rates = [float(s[rate_key]) for s in segments]
    except (KeyError, TypeError, ValueError) as exc:
        return EngineCheckResult(
            engine="arithmetic_check",
            passed=False,
            detail=f"could not extract numeric count/rate from segment_results: {exc}",
        )

    total_from_segments = sum(segment_counts)
    sub_results: List[EngineCheckResult] = []

    counts_match = total_from_segments == evidence_bundle.sample_size
    sub_results.append(
        EngineCheckResult(
            engine="arithmetic_check.segment_counts_sum_to_sample_size",
            passed=counts_match,
            detail=(
                f"sum({count_key} across {len(segments)} segments)="
                f"{total_from_segments} vs sample_size={evidence_bundle.sample_size}"
            ),
            computed=total_from_segments,
            expected=evidence_bundle.sample_size,
        )
    )

    reconstructed_numerator = sum(
        round(rate * count) for rate, count in zip(segment_rates, segment_counts)
    )
    reconstructed_rate = (
        reconstructed_numerator / total_from_segments if total_from_segments else 0.0
    )
    expected_numerator = evidence_bundle.observed_value * evidence_bundle.sample_size
    numerator_diff = abs(reconstructed_numerator - expected_numerator)
    # Integer tolerance: each segment's contribution was itself rounded once,
    # so allow +/-1 unit of slack per segment rather than a tight float bound.
    numerator_tolerance = max(1, len(segments))
    weighted_rate_ok = numerator_diff <= numerator_tolerance

    sub_results.append(
        EngineCheckResult(
            engine="arithmetic_check.weighted_rate_reconciliation",
            passed=weighted_rate_ok,
            detail=(
                f"reconstructed overall value from segments={reconstructed_rate:.4f} "
                f"(numerator~{reconstructed_numerator}) vs recorded "
                f"observed_value={evidence_bundle.observed_value} "
                f"(implied numerator~{expected_numerator:.1f}), "
                f"diff={numerator_diff:.1f}, tolerance=+/-{numerator_tolerance}"
            ),
            computed=reconstructed_rate,
            expected=evidence_bundle.observed_value,
        )
    )

    overall_passed = counts_match and weighted_rate_ok
    return EngineCheckResult(
        engine="arithmetic_check",
        passed=overall_passed,
        detail="; ".join(r.detail for r in sub_results),
        sub_results=sub_results,
    )


# ---------------------------------------------------------------------------
# 3. Provenance re-check
# ---------------------------------------------------------------------------


def _clean_reference(raw: str) -> str:
    """Strip trailing human annotations like ' (this file)' that appear in
    real provenance_chain entries but aren't part of the path/id itself."""
    if " (" in raw and raw.rstrip().endswith(")"):
        return raw[: raw.index(" (")].strip()
    return raw.strip()


def _looks_like_path(ref: str) -> bool:
    return "/" in ref and ref.lower().endswith(_PATH_LIKE_EXTENSIONS)


def find_artifact_by_id(artifacts_dir: Path, artifact_id: str) -> Optional[Path]:
    """
    Resolve a bare reference (e.g. "plan_tier_pro_cohort" or
    "exception_concentration_plan_tier") to a file on disk. Real
    artifacts are inconsistent about how they're referenced:

      - DiagnosticRecord has its own `diagnostic_id` field matching the
        filename stem -- resolved by field match.
      - BenchmarkRecord has NO internal id field at all; the only thing
        that ties "plan_tier_pro_cohort" (as referenced from the finding)
        back to a file is that plan_tier_pro_cohort.json is its filename
        -- resolved by filename-stem fallback.

    Tries id-field match first, falls back to filename-stem match.
    Returns None if neither resolves.
    """
    if not artifacts_dir.exists():
        return None

    stem_match: Optional[Path] = None
    for path in artifacts_dir.rglob("*.json"):
        if path.stem == artifact_id:
            stem_match = path  # keep looking in case a field-match is more precise
        try:
            import json as _json

            data = _json.loads(path.read_text())
        except (ValueError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        for field_name in _ID_FIELD_CANDIDATES:
            if data.get(field_name) == artifact_id:
                return path

    return stem_match


def verify_provenance(artifact: Any, repo_root: Path = Path(".")) -> EngineCheckResult:
    """
    Verifies that every file-path-shaped reference in the artifact's
    provenance-carrying fields (`provenance_chain`, `evidence_ids`,
    `linked_diagnostics`, `linked_metric_gaps` -- whichever exist on the
    given model) actually resolves to a file on disk, either directly
    (it already looks like a relative path) or via find_artifact_by_id.

    Known, deliberately-surfaced-rather-than-hidden data quirk: some
    provenance_chain entries are genuinely NOT file paths, e.g.
    EvidenceBundle's own chain contains the free-text entry
    "MetricContract order_straight_through_rate v1" rather than a path
    to registry/metric_registry/order_straight_through_rate.json. Such
    entries are attempted via find_artifact_by_id's fallback logic but
    reported as a soft note (not a hard FAIL) when they can't be
    resolved, since this is an existing inconsistency in how upstream
    layers write provenance_chain, not something this checker
    introduces. Recommendation flagged: standardize provenance_chain
    entries to always be actual relative file paths going forward.
    """
    artifacts_dir = repo_root / "artifacts"

    reference_fields = (
        "provenance_chain",
        "evidence_ids",
        "linked_diagnostics",
        "linked_metric_gaps",
        "checked_records",
    )

    references: List[str] = []
    for field_name in reference_fields:
        value = getattr(artifact, field_name, None)
        if isinstance(value, list):
            references.extend(str(v) for v in value)

    if not references:
        return EngineCheckResult(
            engine="provenance_check",
            passed=True,
            detail="no provenance-carrying fields present on this artifact type",
        )

    sub_results: List[EngineCheckResult] = []
    for raw_ref in references:
        ref = _clean_reference(raw_ref)

        if _looks_like_path(ref):
            resolved = (repo_root / ref).exists()
            sub_results.append(
                EngineCheckResult(
                    engine="provenance_check.path",
                    passed=resolved,
                    detail=f"{ref!r} {'exists' if resolved else 'DOES NOT EXIST'} under {repo_root}",
                )
            )
            continue

        found = find_artifact_by_id(artifacts_dir, ref)
        if found is not None:
            sub_results.append(
                EngineCheckResult(
                    engine="provenance_check.id_lookup",
                    passed=True,
                    detail=f"{ref!r} resolved to {found}",
                )
            )
        else:
            # Soft note, not a hard failure -- see docstring. Free-text
            # descriptive references (e.g. "MetricContract X v1") are a
            # known upstream inconsistency, not a broken provenance link.
            sub_results.append(
                EngineCheckResult(
                    engine="provenance_check.unresolved",
                    passed=True,
                    detail=(
                        f"{ref!r} did not resolve to a file by path or id lookup "
                        "-- treated as a descriptive (non-file) reference, not a "
                        "failure; flag for provenance_chain standardization"
                    ),
                )
            )

    hard_failures = [r for r in sub_results if not r.passed]
    overall_passed = len(hard_failures) == 0

    return EngineCheckResult(
        engine="provenance_check",
        passed=overall_passed,
        detail=(
            f"{len(references)} reference(s) checked, "
            f"{len(hard_failures)} unresolved path failure(s)"
        ),
        sub_results=sub_results,
    )


# ---------------------------------------------------------------------------
# 4. Composition into a typed VerificationResult
# ---------------------------------------------------------------------------


def run_deterministic_verification(
    *,
    verification_id: str,
    evidence_bundle: EvidenceBundle,
    db_path: str,
    finding_for_provenance: Optional[Any] = None,
    repo_root: Path = Path("."),
    retry_count: int = 0,
) -> VerificationResult:
    """
    Runs the three deterministic engines and assembles a typed
    VerificationResult. semantic_check, benchmark_check, contradiction_check,
    and narrative_integrity are NOT computed here -- those require the
    adversarial-review (LLM) half of L10 that this module deliberately
    does not implement (see module docstring). They're reported as
    "NOT_RUN -- deterministic engine only" so a caller can see exactly
    what was and wasn't checked, rather than a stub silently claiming PASS.

    Disposition logic (mirrors the release-rule table in the architecture
    doc for the checks this module CAN make):
      - REJECT   if query_reexecution or arithmetic_check fails outright
      - LOW_CONFIDENCE if provenance_check has unresolved hard path failures
        but the numeric checks pass
      - PASS     if query_reexecution, arithmetic_check, and provenance_check
        all pass

    This function intentionally cannot emit PASS on the full 7-engine
    contract by itself -- semantic/benchmark/contradiction checks are
    marked NOT_RUN, so a caller wiring this into the full L10 skill must
    still run the adversarial half before treating disposition as final.
    """
    not_run = "NOT_RUN -- deterministic engine only, requires adversarial-review pass"

    query_result = verify_query_reexecution(evidence_bundle, db_path)
    arithmetic_result = verify_arithmetic(evidence_bundle)

    provenance_target = finding_for_provenance if finding_for_provenance is not None else evidence_bundle
    provenance_result = verify_provenance(provenance_target, repo_root=repo_root)

    if not query_result.passed or not arithmetic_result.passed:
        disposition: str = "REJECT"
    elif not provenance_result.passed:
        disposition = "LOW_CONFIDENCE"
    else:
        disposition = "PASS"

    engine_results = EngineResults(
        semantic_check=not_run,
        query_reexecution=query_result.to_status_string(),
        arithmetic_check=arithmetic_result.to_status_string(),
        data_quality_check=f"data_quality_status={evidence_bundle.data_quality_status} (from EvidenceBundle, not independently re-derived)",
        benchmark_check=not_run,
        contradiction_check=not_run,
        provenance_check=provenance_result.to_status_string(),
        narrative_integrity=None,
    )

    notes = (
        f"Deterministic engines only. query_reexecution={query_result.passed}, "
        f"arithmetic_check={arithmetic_result.passed}, "
        f"provenance_check={provenance_result.passed}. "
        "semantic_check/benchmark_check/contradiction_check require the "
        "adversarial-review half of L10 and were not run by this module."
    )

    return VerificationResult(
        verification_id=verification_id,
        checked_records=[evidence_bundle.evidence_id],
        engine_results=engine_results,
        disposition=disposition,  # type: ignore[arg-type]
        retry_count=retry_count,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# 5. Subprocess-isolated verification (real process isolation)
# ---------------------------------------------------------------------------

import json as _json
import subprocess
import sys as _sys


def run_deterministic_verification_subprocess(
    *,
    verification_id: str,
    evidence_bundle: EvidenceBundle,
    db_path: str,
    finding_for_provenance: Optional[Any] = None,
    repo_root: Path = Path("."),
    retry_count: int = 0,
    python_executable: Optional[str] = None,
    timeout_seconds: float = 30.0,
) -> VerificationResult:
    """
    The genuinely process-isolated counterpart to run_deterministic_verification.
    Same signature, same return type -- the only difference is that this
    version runs the actual verification in a brand-new `python
    engine/verifier_worker.py` subprocess rather than in-process. Use
    this one in the orchestrator; the in-process version above remains
    available for unit-testing individual engines cheaply (no subprocess
    overhead) and is what verifier_worker.py itself calls internally.

    Independence this actually buys, that the in-process version cannot:
    the subprocess has its own interpreter, its own memory, and zero
    access to any variable, import, or object that exists in the calling
    process -- including whatever produced evidence_bundle in the first
    place. Communication happens ONLY through the stdin/stdout JSON
    contract documented in verifier_worker.py's module docstring.
    """
    worker_path = Path(__file__).resolve().parent / "verifier_worker.py"
    python_executable = python_executable or _sys.executable

    payload = {
        "record_under_test": evidence_bundle.model_dump(mode="json"),
        "source_reference": db_path,
        "verification_policy": {
            "finding_for_provenance": (
                finding_for_provenance.model_dump(mode="json")
                if finding_for_provenance is not None
                else None
            ),
            "repo_root": str(repo_root),
            "verification_id": verification_id,
            "retry_count": retry_count,
        },
    }

    try:
        proc = subprocess.run(
            [python_executable, str(worker_path)],
            input=_json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise VerificationError(
            f"verifier subprocess timed out after {timeout_seconds}s: {exc}"
        ) from exc

    if proc.returncode != 0:
        raise VerificationError(
            f"verifier subprocess exited {proc.returncode}: {proc.stderr.strip()}"
        )

    try:
        result_dict = _json.loads(proc.stdout)
    except _json.JSONDecodeError as exc:
        raise VerificationError(
            f"verifier subprocess produced non-JSON stdout: {proc.stdout[:300]!r}"
        ) from exc

    return VerificationResult.model_validate(result_dict)
