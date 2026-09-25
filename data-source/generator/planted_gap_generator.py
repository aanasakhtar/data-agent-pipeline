#!/usr/bin/env python3
"""
data-source/generator/planted_gap_generator.py
=================================================
Builds a SEPARATE, self-contained DuckDB warehouse containing a
deliberately planted, exactly-known operational gap -- unlike the
existing Faker-driven generate_data.py, which produces realistic but
UNCONTROLLED counts (the pilot's 90.47% STP rate is whatever the random
seed happened to produce, not a designed value).

Design choice: reuses the EXACT same gold-layer schema as the real
pilot warehouse (gold.fct_orders / gold.fct_support_tickets /
gold.dim_customers, same column names and types) so the pilot's own
already-verified MetricContract and executable_query_template work
UNCHANGED against this database. The only thing that differs is the
underlying data -- which is the entire point: this proves the pipeline
can discover a real gap using the same machinery already proven on the
pilot's baseline, not a specially-shaped scenario that only works
because the code was tuned to it.

The gap is planted as an EXACT, hand-computed set of integer counts
(not sampled from a random distribution that only approximately hits a
target rate), specifically so the "known ground truth" in the emitted
scenario file is exact, not a statistical approximation:

    plan_tier    completed_orders   no_ticket_orders   rate
    enterprise   150                144                0.9600
    free         650                624                0.9600
    pro          300                180                0.6000   <- planted concentrated problem
    -----------------------------------------------------------
    TOTAL        1100               948                0.8618

The "pro" tier's 60% rate against an otherwise-healthy 96% baseline is
the planted, concentrated exception/rework problem -- consistent with
the ask's "high rework/exception rate concentrated in a specific
workflow/segment alongside a normal baseline."

Ground-truth financial values are computed here with PLAIN, independent
arithmetic (not by importing/calling engine.value.compute_value_record)
on purpose: comparing the live pipeline's output against a SEPARATELY
derived expectation is what makes the end-to-end test in test_p1.py
meaningful rather than circular. See the module docstring of
engine/run_affirmative_pipeline.py for how these numbers get compared
against the live-computed ValueRecord.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

import duckdb
from faker import Faker

SEED = 20260923  # arbitrary but fixed -- reproducibility of the customer-record cosmetics (names/emails/dates), NOT of the planted counts, which are exact integers regardless of seed.

# Exact planted counts -- see module docstring table.
SEGMENT_PLAN: Dict[str, Dict[str, int]] = {
    "enterprise": {"completed_orders": 150, "no_ticket_orders": 144},
    "free": {"completed_orders": 650, "no_ticket_orders": 624},
    "pro": {"completed_orders": 300, "no_ticket_orders": 180},  # planted concentrated gap
}

STATED_TARGET_STP = 0.90
BUSINESS_FUNCTION = "Order Fulfillment & Support (Planted-Gap Scenario)"
CUSTOMER_STATED_TEXT = (
    "We want our straight-through order processing rate at 90% across all "
    "plan tiers -- right now it feels like our Pro-tier orders are "
    "generating a lot more support tickets than they should, but we don't "
    "have hard numbers on it."
)

ROLE_ROSTER = {
    "role_name": "Fulfillment & Exception Handling Specialist",
    "headcount": 20,
    "salary_source": 58000.0,
    "overhead_multiplier": 1.25,
    "pct_time_on_function": 0.5,
    "pct_automatable": 0.7,
    "realization_mode": "blended",
    "blended_cash_ratio": 0.5,
    "realization_factor": 0.8,
}


@dataclass
class GroundTruth:
    scenario_id: str
    business_function: str
    customer_stated_text: str
    stated_target_stp: float
    segment_plan: Dict[str, Dict[str, int]]
    total_completed_orders: int
    total_no_ticket_orders: int
    expected_observed_value: float
    expected_gap_fraction: float
    role_roster: Dict[str, object]
    expected_addressable_labor_pool: float
    expected_total_annual_unlock: float
    expected_cash_benefit: float
    expected_capacity_benefit: float
    db_path: str
    generated_at: str


def _compute_ground_truth(db_path: Path) -> GroundTruth:
    """
    Plain, independent arithmetic -- deliberately NOT calling
    engine.value.compute_value_record (see module docstring).
    """
    total_completed = sum(s["completed_orders"] for s in SEGMENT_PLAN.values())
    total_no_ticket = sum(s["no_ticket_orders"] for s in SEGMENT_PLAN.values())
    observed_value = round(total_no_ticket / total_completed, 4)
    gap_fraction = round(STATED_TARGET_STP - observed_value, 6)
    gap_fraction = max(0.0, gap_fraction)

    roster = ROLE_ROSTER
    addressable_labor_pool = (
        roster["headcount"]
        * roster["salary_source"]
        * roster["overhead_multiplier"]
        * roster["pct_time_on_function"]
        * roster["pct_automatable"]
    )
    total_annual_unlock = round(addressable_labor_pool * gap_fraction * roster["realization_factor"], 2)
    cash_benefit = round(total_annual_unlock * roster["blended_cash_ratio"], 2)
    capacity_benefit = round(total_annual_unlock - cash_benefit, 2)

    return GroundTruth(
        scenario_id="planted-gap-pro-tier-stp-v1",
        business_function=BUSINESS_FUNCTION,
        customer_stated_text=CUSTOMER_STATED_TEXT,
        stated_target_stp=STATED_TARGET_STP,
        segment_plan=SEGMENT_PLAN,
        total_completed_orders=total_completed,
        total_no_ticket_orders=total_no_ticket,
        expected_observed_value=observed_value,
        expected_gap_fraction=gap_fraction,
        role_roster=roster,
        expected_addressable_labor_pool=round(addressable_labor_pool, 2),
        expected_total_annual_unlock=total_annual_unlock,
        expected_cash_benefit=cash_benefit,
        expected_capacity_benefit=capacity_benefit,
        db_path=str(db_path),
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def _build_customers(fake: Faker, plan_tier: str, n: int, start_id: int) -> List[dict]:
    rows = []
    for i in range(n):
        cid = f"CUST-{plan_tier[:3].upper()}-{start_id + i:05d}"
        rows.append(
            {
                "customer_id": cid,
                "first_name": fake.first_name(),
                "last_name": fake.last_name(),
                "email": fake.unique.email(),
                "phone": fake.phone_number(),
                "company": fake.company(),
                "country": fake.country(),
                "plan_tier": plan_tier,
                "customer_status": "active",
                "signup_date": fake.date_between(start_date="-2y", end_date="-30d"),
                "plan_status_effective_from": fake.date_between(start_date="-2y", end_date="-30d"),
            }
        )
    return rows


def _build_orders_and_tickets(
    fake: Faker, plan_tier: str, customers: List[dict], completed: int, no_ticket: int
) -> tuple[List[dict], List[dict]]:
    """
    Builds exactly `completed` completed orders for this segment, of
    which exactly `no_ticket` have NO linked support ticket (straight-
    through) and the remaining (completed - no_ticket) DO have a linked
    ticket (the planted friction). Order/customer assignment is
    round-robin over the segment's customer pool -- cosmetic only, does
    not affect the counts.
    """
    orders: List[dict] = []
    tickets: List[dict] = []
    base_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
    order_seq = 0
    ticket_seq = 0

    with_ticket = completed - no_ticket

    for i in range(completed):
        order_seq += 1
        oid = f"ORD-{plan_tier[:3].upper()}-{order_seq:06d}"
        customer = customers[i % len(customers)]
        order_date = base_date + timedelta(days=i % 90, hours=i % 24)
        orders.append(
            {
                "order_id": oid,
                "customer_id": customer["customer_id"],
                "order_date": order_date,
                "order_status": "completed",
                "order_total": round(fake.pyfloat(min_value=20, max_value=2000, right_digits=2), 2),
                "item_count": 1 + (i % 5),
                "total_quantity": 1 + (i % 8),
            }
        )
        if i < with_ticket:
            ticket_seq += 1
            created = order_date + timedelta(hours=2 + (i % 10))
            resolved = created + timedelta(hours=4 + (i % 20))
            tickets.append(
                {
                    "ticket_id": f"TCK-{plan_tier[:3].upper()}-{ticket_seq:06d}",
                    "customer_id": customer["customer_id"],
                    "order_id": oid,
                    "priority": ["low", "medium", "high"][i % 3],
                    "ticket_status": "resolved",
                    "category": "order_discrepancy",
                    "csat_score": 3.0,
                    "created_at": created,
                    "resolved_at": resolved,
                    "resolution_hours": (resolved - created).total_seconds() / 3600,
                }
            )

    return orders, tickets


def build_planted_gap_scenario(
    output_dir: Path | str = "data-source/generator/output/planted_gap",
) -> GroundTruth:
    """
    Builds the planted-gap DuckDB warehouse and writes a companion
    scenario_ground_truth.json alongside it. Idempotent: re-running
    overwrites both files with the same content (SEGMENT_PLAN and
    ROLE_ROSTER are fixed constants, not randomly sampled).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    db_path = output_dir / "planted_gap.duckdb"

    fake = Faker()
    Faker.seed(SEED)

    all_customers: List[dict] = []
    all_orders: List[dict] = []
    all_tickets: List[dict] = []
    start_id = 1
    for plan_tier, counts in SEGMENT_PLAN.items():
        n_customers = max(10, counts["completed_orders"] // 10)
        customers = _build_customers(fake, plan_tier, n_customers, start_id)
        start_id += n_customers
        orders, tickets = _build_orders_and_tickets(
            fake, plan_tier, customers, counts["completed_orders"], counts["no_ticket_orders"]
        )
        all_customers.extend(customers)
        all_orders.extend(orders)
        all_tickets.extend(tickets)

    if db_path.exists():
        db_path.unlink()  # rebuild clean rather than risk stale leftover tables from a prior schema version

    con = duckdb.connect(str(db_path))
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS gold")

        con.execute(
            """
            CREATE TABLE gold.dim_customers (
                customer_id VARCHAR, first_name VARCHAR, last_name VARCHAR,
                email VARCHAR, phone VARCHAR, company VARCHAR, country VARCHAR,
                plan_tier VARCHAR, customer_status VARCHAR,
                signup_date DATE, plan_status_effective_from DATE
            )
            """
        )
        con.executemany(
            "INSERT INTO gold.dim_customers VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    c["customer_id"], c["first_name"], c["last_name"], c["email"], c["phone"],
                    c["company"], c["country"], c["plan_tier"], c["customer_status"],
                    c["signup_date"], c["plan_status_effective_from"],
                )
                for c in all_customers
            ],
        )

        con.execute(
            """
            CREATE TABLE gold.fct_orders (
                order_id VARCHAR, customer_id VARCHAR, order_date TIMESTAMP,
                order_date_day DATE, order_status VARCHAR, order_total DOUBLE,
                item_count INTEGER, total_quantity INTEGER
            )
            """
        )
        con.executemany(
            "INSERT INTO gold.fct_orders VALUES (?,?,?,?,?,?,?,?)",
            [
                (
                    o["order_id"], o["customer_id"], o["order_date"], o["order_date"].date(),
                    o["order_status"], o["order_total"], o["item_count"], o["total_quantity"],
                )
                for o in all_orders
            ],
        )

        con.execute(
            """
            CREATE TABLE gold.fct_support_tickets (
                ticket_id VARCHAR, customer_id VARCHAR, order_id VARCHAR,
                priority VARCHAR, ticket_status VARCHAR, category VARCHAR,
                csat_score DOUBLE, created_at TIMESTAMP, resolved_at TIMESTAMP,
                resolution_hours DOUBLE
            )
            """
        )
        con.executemany(
            "INSERT INTO gold.fct_support_tickets VALUES (?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    t["ticket_id"], t["customer_id"], t["order_id"], t["priority"],
                    t["ticket_status"], t["category"], t["csat_score"],
                    t["created_at"], t["resolved_at"], t["resolution_hours"],
                )
                for t in all_tickets
            ],
        )

        # Sanity-check the planted counts against what was actually written,
        # before ever handing this database to the pipeline -- if this
        # assertion ever fails, the generator itself has a bug, and it's
        # much better to fail loudly here than to silently ship a database
        # that doesn't match its own ground-truth file.
        check = con.execute(
            """
            select
                count(distinct o.order_id) as completed_orders,
                count(distinct o.order_id) filter (where t.order_id is null) as no_ticket_orders
            from gold.fct_orders o
            left join gold.fct_support_tickets t on o.order_id = t.order_id
            where o.order_status = 'completed'
            """
        ).fetchone()
        expected_total = sum(s["completed_orders"] for s in SEGMENT_PLAN.values())
        expected_no_ticket = sum(s["no_ticket_orders"] for s in SEGMENT_PLAN.values())
        if check[0] != expected_total or check[1] != expected_no_ticket:
            raise RuntimeError(
                f"planted-gap generator self-check FAILED: warehouse contains "
                f"completed_orders={check[0]}, no_ticket_orders={check[1]}, "
                f"expected {expected_total}/{expected_no_ticket} -- refusing to "
                "emit a ground-truth file that wouldn't match the data"
            )
    finally:
        con.close()

    ground_truth = _compute_ground_truth(db_path)
    ground_truth_path = output_dir / "scenario_ground_truth.json"
    ground_truth_path.write_text(json.dumps(ground_truth.__dict__, indent=2))

    return ground_truth


if __name__ == "__main__":
    gt = build_planted_gap_scenario()
    print(f"Built planted-gap warehouse at {gt.db_path}")
    print(f"Expected observed_value: {gt.expected_observed_value}")
    print(f"Expected gap_fraction:   {gt.expected_gap_fraction}")
    print(f"Expected total_annual_unlock: {gt.expected_total_annual_unlock}")
