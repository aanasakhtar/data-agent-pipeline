"""
engine/evidence.py
====================
Live Layer 6: takes a validated MetricContract and a database path,
actually runs the contract's query against the warehouse, and
constructs a fully-validated EvidenceBundle -- no static JSON file
involved. This is what turns the pipeline from "replays one recorded
pilot run" into "measures whatever is actually in the database right
now for whatever contract L4/L5 produced."

Conventions inherited from verifier.py, stated explicitly here rather
than silently re-assumed:

  - The metric's own value is the LAST column of the single row the
    overall query returns (see verifier.verify_query_reexecution's
    docstring -- same fragile-by-convention assumption, same
    recommendation to eventually add an explicit
    `result_value_column: str` field to MetricContract).
  - This module additionally assumes the overall query returns exactly
    3 columns in the shape (denominator, numerator, rate) -- true for
    the one real query in this repo (completed_orders, no_ticket_orders,
    straight_through_rate) and for the planted-gap scenario's identical
    query. A contract whose query returns a different column count is
    handled by falling back to sample_size=None-safe defaults rather
    than guessing wrong -- see _extract_counts.

Segmentation is NOT computed by rewriting the base query's SQL (fragile,
error-prone string surgery). Instead, this module looks up a
PRE-VERIFIED segmented query from registry/verified_queries/<metric_id>.yml
-- entries named `<metric_id>_by_<dimension>` -- for each dimension in
contract.dimensions. If no such verified entry exists for a dimension,
segmentation for that dimension is skipped with an explicit caveat
rather than invented.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import duckdb
import yaml

from engine.gates import parse_minimum_sample_size
from engine.schemas import EvidenceBundle, MetricContract, compute_query_hash


class EvidenceExecutionError(Exception):
    """Raised for operational failures executing L6 -- bad SQL, missing
    database, or a result shape this module doesn't know how to
    interpret. Distinct from a normal low/zero result, which is a valid
    EvidenceBundle, not an error."""


def _load_verified_queries(repo_root: Path, metric_id: str) -> Dict[str, dict]:
    """
    Reads registry/verified_queries/<metric_id>.yml (Cortex-Analyst-style
    Verified Query Repository -- see that file's own header comment).
    Returns {} if the file doesn't exist rather than raising: not every
    metric will have a segmented entry yet, and that's a caveat, not a
    hard failure.
    """
    path = repo_root / "registry" / "verified_queries" / f"{metric_id}.yml"
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise EvidenceExecutionError(f"malformed verified-query registry file {path}: {exc}") from exc
    entries = {}
    for entry in data.get("verified_queries", []):
        name = entry.get("name")
        if name:
            entries[name] = entry
    return entries


def _extract_counts(row: Tuple[Any, ...]) -> Tuple[Optional[float], Optional[float], float]:
    """
    Returns (denominator, numerator, observed_value) from a single result
    row, per the 3-column (denominator, numerator, rate) convention
    documented in the module docstring. Falls back to (None, None,
    last_column) for any other column count rather than guessing which
    columns are which.
    """
    if len(row) == 3:
        denominator, numerator, rate = row
        return float(denominator), float(numerator), float(rate)
    return None, None, float(row[-1])


def execute_evidence(
    contract: MetricContract,
    db_path: str,
    *,
    evidence_id: Optional[str] = None,
    repo_root: Path = Path("."),
    run_id: Optional[str] = None,
    period_label: Optional[str] = None,
) -> EvidenceBundle:
    """
    The actual live L6 step. Pure with respect to the database's current
    contents -- calling this twice against an unchanged warehouse
    produces the same EvidenceBundle (modulo execution_timestamp/
    evidence_id/run_id, which are metadata about the RUN, not the
    measurement).
    """
    if not Path(db_path).exists():
        raise EvidenceExecutionError(f"database not found at {db_path!r}")

    query = contract.executable_query_template
    if not query.strip():
        raise EvidenceExecutionError(
            f"MetricContract {contract.metric_id!r} has an empty executable_query_template "
            "-- this should have been caught by engine.gates.metric_contract_gate before "
            "reaching L6"
        )

    con = duckdb.connect(db_path, read_only=True)
    try:
        try:
            rows = con.execute(query).fetchall()
        except Exception as exc:  # noqa: BLE001 -- surfacing as a clear operational error
            raise EvidenceExecutionError(
                f"executable_query_template failed against {db_path}: {exc}"
            ) from exc
    finally:
        con.close()

    if len(rows) != 1:
        raise EvidenceExecutionError(
            f"expected exactly 1 row from the overall query, got {len(rows)} -- "
            "this module only handles single-row aggregate contracts today"
        )

    denominator, numerator, observed_value = _extract_counts(rows[0])
    sample_size = int(denominator) if denominator is not None else 0
    if denominator is None:
        raise EvidenceExecutionError(
            f"could not determine sample_size from a {len(rows[0])}-column result "
            f"row {rows[0]!r} -- executable_query_template must return exactly 3 "
            "columns (denominator, numerator, rate) for this module to interpret it "
            "safely; see module docstring"
        )

    segment_results, distribution_summary, segmentation_caveats = _compute_segments(
        contract, db_path, repo_root
    )

    now = datetime.now(timezone.utc)
    evidence_id = evidence_id or f"{contract.metric_id}_{now.strftime('%Y%m%dT%H%M%SZ')}"

    min_sample = parse_minimum_sample_size(contract.minimum_sample_guidance)
    if min_sample is not None and sample_size >= min_sample:
        data_quality_status = "HIGH"
    elif sample_size > 0:
        data_quality_status = "MEDIUM"
    else:
        data_quality_status = "UNUSABLE"

    caveats: List[str] = list(segmentation_caveats)

    bundle = EvidenceBundle(
        evidence_id=evidence_id,
        metric_contract_id=f"{contract.metric_id}:{contract.version}",
        observed_value=round(observed_value, 4),
        period=period_label or now.strftime("%Y"),
        sample_size=sample_size,
        distribution_summary=distribution_summary,
        trend_summary="single-period live measurement; no historical trend comparison implemented yet",
        segment_results=segment_results,
        source_objects=list(contract.source_entities),
        query=query,
        query_hash=compute_query_hash(query),
        execution_timestamp=now.isoformat(),
        data_quality_status=data_quality_status,  # type: ignore[arg-type]
        freshness_status="live query executed at run time -- no staleness possible by construction",
        source_coverage="full scan of source_entities, no sampling",
        caveats=caveats,
        provenance_chain=[
            f"MetricContract {contract.metric_id} v{contract.version}",
            f"live executable_query_template against {db_path}",
        ],
        numerator=numerator,
        denominator=denominator,
        result_hash=compute_query_hash(str(rows[0])),
        execution_id=f"exec_{now.strftime('%Y%m%dT%H%M%S%f')}Z",
        source_snapshot_ids=[],
        run_id=run_id,
    )
    return bundle


def _compute_segments(
    contract: MetricContract, db_path: str, repo_root: Path
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], List[str]]:
    if not contract.dimensions:
        return [], {}, []

    verified_queries = _load_verified_queries(repo_root, contract.metric_id)
    segment_results: List[Dict[str, Any]] = []
    distribution_summary: Dict[str, Any] = {}
    caveats: List[str] = []

    con = duckdb.connect(db_path, read_only=True)
    try:
        for dimension in contract.dimensions:
            entry_name = f"{contract.metric_id}_by_{dimension}"
            entry = verified_queries.get(entry_name)
            if entry is None:
                caveats.append(
                    f"segmentation by {dimension!r} skipped: no verified segmented query "
                    f"named {entry_name!r} found in registry/verified_queries/"
                    f"{contract.metric_id}.yml"
                )
                continue

            sql = entry.get("sql")
            if not sql or not str(sql).strip():
                caveats.append(f"segmentation by {dimension!r} skipped: registry entry {entry_name!r} has no sql")
                continue

            try:
                rows = con.execute(sql).fetchall()
                col_names = [d[0] for d in con.description] if con.description else []
            except Exception as exc:  # noqa: BLE001
                caveats.append(f"segmentation by {dimension!r} failed to execute: {exc}")
                continue

            by_segment: Dict[str, float] = {}
            for row in rows:
                row_dict = dict(zip(col_names, row))
                segment_results.append(row_dict)
                seg_key = row_dict.get(dimension)
                rate_cols = [k for k in row_dict if "rate" in k.lower()]
                if seg_key is not None and rate_cols:
                    by_segment[str(seg_key)] = row_dict[rate_cols[0]]
            if by_segment:
                distribution_summary[f"by_{dimension}"] = by_segment
    finally:
        con.close()

    return segment_results, distribution_summary, caveats
