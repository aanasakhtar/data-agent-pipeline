from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from engine.schemas import (  # noqa: E402
    AIOpportunityRecord,
    BenchmarkRecord,
    BusinessFunctionContext,
    DiagnosticRecord,
    EvidenceBundle,
    FindingDraft,
    MetricContract,
    VerificationResult,
)


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def db_path(repo_root: Path) -> str:
    path = repo_root / "dbt" / "customer_platform" / "dev.duckdb"
    if not path.exists():
        pytest.skip(
            f"dev.duckdb not found at {path} -- run `dbt build --target local` "
            "from dbt/customer_platform/ first (HANDOFF.md Part 4)"
        )
    return str(path)


def _load(repo_root: Path, rel_path: str, model):
    return model.model_validate(json.loads((repo_root / rel_path).read_text()))


@pytest.fixture(scope="session")
def business_context(repo_root):
    return _load(repo_root, "artifacts/business_context/order-fulfillment.json", BusinessFunctionContext)


@pytest.fixture(scope="session")
def metric_contract(repo_root):
    return _load(repo_root, "artifacts/metric_contracts/order_straight_through_rate.json", MetricContract)


@pytest.fixture(scope="session")
def evidence(repo_root):
    return _load(
        repo_root,
        "artifacts/evidence/order_straight_through_rate_20260918T161600Z.json",
        EvidenceBundle,
    )


@pytest.fixture(scope="session")
def diagnostic_exception_concentration(repo_root):
    return _load(
        repo_root, "artifacts/diagnostics/exception_concentration_plan_tier.json", DiagnosticRecord
    )


@pytest.fixture(scope="session")
def diagnostic_process_variant(repo_root):
    return _load(repo_root, "artifacts/diagnostics/process_variant_analysis.json", DiagnosticRecord)


@pytest.fixture(scope="session")
def ai_opportunity(repo_root):
    return _load(
        repo_root, "artifacts/ai_opportunities/order-fulfillment-ai-assessment.json", AIOpportunityRecord
    )


@pytest.fixture(scope="session")
def benchmark(repo_root):
    return _load(repo_root, "artifacts/benchmarks/plan_tier_pro_cohort.json", BenchmarkRecord)


@pytest.fixture(scope="session")
def stored_verification(repo_root):
    return _load(
        repo_root, "artifacts/verification/order_straight_through_rate_v1_verify.json", VerificationResult
    )


@pytest.fixture(scope="session")
def finding(repo_root):
    return _load(
        repo_root, "artifacts/findings/order-straight-through-rate-pilot-1.json", FindingDraft
    )
