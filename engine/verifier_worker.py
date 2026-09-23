#!/usr/bin/env python3
"""
engine/verifier_worker.py
===========================
Standalone entrypoint, run as a SEPARATE OS PROCESS via subprocess.run
(see verifier.run_deterministic_verification_subprocess). This is the
real fix for the gap named plainly in the last review: opening a second
DuckDB connection inside the same Python process is isolation of state,
not isolation of PROCESS -- a fresh interpreter with its own memory space
is what the blueprint's section 4.3 and the MARCH paper's
information-asymmetry argument actually call for.

Contract (matches the blueprint's section 4.3 JSON shape):

  STDIN  (JSON):
    {
      "record_under_test": <EvidenceBundle as dict>,
      "source_reference": "<db_path>",
      "verification_policy": {
        "finding_for_provenance": <FindingDraft as dict, or null>,
        "repo_root": "<path>",
        "verification_id": "...",
        "retry_count": 0
      }
    }

  STDOUT (JSON): a VerificationResult, exactly as run_deterministic_verification
  returns it -- the parent process parses this back into a typed object.

  Exit code 0 on a completed verification (regardless of PASS/REJECT --
  a REJECT is a successful verification run that found a problem, not a
  crash). Non-zero exit means the verification itself could not run
  (bad input, missing database, etc.) -- the parent treats that as an
  operational failure, not a disposition.

Deliberately absent from the input contract, per the blueprint's "should
NOT receive" list: any producer reasoning trace, chain-of-thought, or
out-of-band "expected answer" framing. What IS present --
record_under_test's own observed_value -- is not that: it's the artifact
under test, not a hint. This process has no access to whatever prompt or
reasoning produced record_under_test; it only ever sees the same
structured object a human reviewer would need to check it.

This script imports nothing from a running parent -- it is invoked as
`python verifier_worker.py`, which gets a brand-new interpreter, its own
memory, and zero shared state with whatever process is calling it. That
is the actual isolation guarantee; everything else in this file is just
plumbing to make that guarantee usable.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running as `python engine/verifier_worker.py` from the repo root
# without requiring the package to be installed.
_REPO_ROOT_FOR_IMPORT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT_FOR_IMPORT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT_FOR_IMPORT))

from engine.schemas import EvidenceBundle, FindingDraft  # noqa: E402
from engine.verifier import run_deterministic_verification  # noqa: E402


def main() -> int:
    raw_input = sys.stdin.read()
    try:
        payload = json.loads(raw_input)
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": f"invalid JSON on stdin: {exc}"}), file=sys.stderr)
        return 2

    try:
        evidence = EvidenceBundle.model_validate(payload["record_under_test"])
        db_path = payload["source_reference"]
        policy = payload.get("verification_policy", {})
        finding_raw = policy.get("finding_for_provenance")
        finding = FindingDraft.model_validate(finding_raw) if finding_raw else None
        repo_root = Path(policy.get("repo_root", "."))
        verification_id = policy.get("verification_id", "subprocess-verification")
        retry_count = int(policy.get("retry_count", 0))
    except Exception as exc:  # noqa: BLE001 -- malformed input is an operational failure
        print(json.dumps({"error": f"malformed verification payload: {exc}"}), file=sys.stderr)
        return 2

    try:
        result = run_deterministic_verification(
            verification_id=verification_id,
            evidence_bundle=evidence,
            db_path=db_path,
            finding_for_provenance=finding,
            repo_root=repo_root,
            retry_count=retry_count,
        )
    except Exception as exc:  # noqa: BLE001 -- surface as a clean operational failure, not a traceback the parent has to parse
        print(json.dumps({"error": f"verification run failed: {exc}"}), file=sys.stderr)
        return 1

    print(result.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
