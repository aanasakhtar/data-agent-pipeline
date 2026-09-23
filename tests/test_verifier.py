"""
The corrupted-fixture tests in this file are the thing HANDOFF.md Part 6
flagged as never exercised: "the reject -> retry loop has never actually
been triggered end-to-end." These tests trigger it, deliberately, four
different ways, against the real database.
"""

from __future__ import annotations

import copy
import json

import pytest

from engine.schemas import EvidenceBundle, FindingDraft
from engine.verifier import (
    run_deterministic_verification,
    verify_arithmetic,
    verify_provenance,
    verify_query_reexecution,
)


# ---------------------------------------------------------------------------
# Real-data PASS path
# ---------------------------------------------------------------------------


def test_query_reexecution_passes_on_real_data(evidence, db_path):
    result = verify_query_reexecution(evidence, db_path)
    assert result.passed is True
    assert result.computed == pytest.approx(0.9047, abs=1e-4)


def test_arithmetic_passes_on_real_data(evidence):
    result = verify_arithmetic(evidence)
    assert result.passed is True
    assert len(result.sub_results) == 2
    assert all(r.passed for r in result.sub_results)


def test_provenance_passes_on_real_finding(finding, repo_root):
    result = verify_provenance(finding, repo_root=repo_root)
    assert result.passed is True
    # confirms the " (this file)" annotation on the last chain entry was
    # correctly stripped rather than causing a false FAIL
    assert len(result.sub_results) == 8
    assert all(r.passed for r in result.sub_results)


def test_full_deterministic_verification_passes_on_real_data(evidence, finding, db_path, repo_root):
    result = run_deterministic_verification(
        verification_id="test-real-pass",
        evidence_bundle=evidence,
        db_path=db_path,
        finding_for_provenance=finding,
        repo_root=repo_root,
    )
    assert result.disposition == "PASS"


# ---------------------------------------------------------------------------
# Deliberately corrupted -- exercising the reject path for the first time
# ---------------------------------------------------------------------------


def test_corrupted_observed_value_triggers_reject(evidence, db_path):
    """A wrong headline number must not survive re-execution."""
    bad = evidence.model_copy(update={"observed_value": 0.75})
    result = run_deterministic_verification(
        verification_id="test-corrupt-observed-value", evidence_bundle=bad, db_path=db_path
    )
    assert result.disposition == "REJECT"
    assert "MISMATCH" in result.engine_results.query_reexecution


def test_tampered_query_text_rejected_at_parse_time():
    """A query edited after its hash was computed must never even
    construct a valid EvidenceBundle -- caught before verification runs."""
    import json
    from pathlib import Path
    from pydantic import ValidationError

    raw = json.loads(
        (Path(__file__).resolve().parent.parent
         / "artifacts/evidence/order_straight_through_rate_20260918T161600Z.json").read_text()
    )
    raw["query"] = raw["query"].replace("completed", "cancelled")
    with pytest.raises(ValidationError):
        EvidenceBundle.model_validate(raw)


def test_corrupted_segment_counts_trigger_reject(evidence, db_path):
    """Internal inconsistency between segment_results and sample_size
    must fail the arithmetic engine even when the top-line SQL still
    reproduces (the two engines check different things on purpose)."""
    bad_segments = copy.deepcopy(evidence.segment_results)
    bad_segments[0]["completed_orders"] = 28  # was 93 -- breaks the 965 total
    bad = evidence.model_copy(update={"segment_results": bad_segments})
    result = run_deterministic_verification(
        verification_id="test-corrupt-segments", evidence_bundle=bad, db_path=db_path
    )
    assert result.disposition == "REJECT"
    assert "FAIL" in result.engine_results.arithmetic_check


def test_broken_provenance_path_triggers_low_confidence(evidence, finding, db_path, repo_root):
    """A broken provenance link should downgrade to LOW_CONFIDENCE, not
    a hard REJECT -- the numbers are still fine, only the paper trail
    to one upstream file is broken."""
    bad_chain = list(finding.provenance_chain)
    bad_chain[0] = "artifacts/business_context/DOES-NOT-EXIST.json"
    bad_finding = finding.model_copy(update={"provenance_chain": bad_chain})

    result = run_deterministic_verification(
        verification_id="test-broken-provenance",
        evidence_bundle=evidence,
        db_path=db_path,
        finding_for_provenance=bad_finding,
        repo_root=repo_root,
    )
    assert result.disposition == "LOW_CONFIDENCE"
    assert "FAIL" in result.engine_results.provenance_check


def test_query_reexecution_raises_on_missing_database(evidence):
    from engine.verifier import VerificationError

    with pytest.raises(VerificationError):
        verify_query_reexecution(evidence, "/nonexistent/path/dev.duckdb")


# ---------------------------------------------------------------------------
# Genuine subprocess (OS-process) isolation -- the gap named in the last
# review: opening a second DuckDB connection in the SAME process is
# isolation of state, not isolation of process. These tests exercise the
# real subprocess path.
# ---------------------------------------------------------------------------


def test_subprocess_verification_passes_on_real_data(evidence, finding, db_path, repo_root):
    from engine.verifier import run_deterministic_verification_subprocess

    result = run_deterministic_verification_subprocess(
        verification_id="subprocess-test-pass",
        evidence_bundle=evidence,
        db_path=db_path,
        finding_for_provenance=finding,
        repo_root=repo_root,
    )
    assert result.disposition == "PASS"


def test_subprocess_verification_rejects_corrupted_evidence(evidence, db_path):
    from engine.verifier import run_deterministic_verification_subprocess

    bad = evidence.model_copy(update={"observed_value": 0.5})
    result = run_deterministic_verification_subprocess(
        verification_id="subprocess-test-reject", evidence_bundle=bad, db_path=db_path
    )
    assert result.disposition == "REJECT"
    assert "MISMATCH" in result.engine_results.query_reexecution


def test_subprocess_raises_operational_error_on_bad_db_path(evidence, repo_root):
    from engine.verifier import VerificationError, run_deterministic_verification_subprocess

    with pytest.raises(VerificationError):
        run_deterministic_verification_subprocess(
            verification_id="subprocess-test-badpath",
            evidence_bundle=evidence,
            db_path="/nonexistent/dev.duckdb",
            repo_root=repo_root,
        )
