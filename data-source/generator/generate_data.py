"""
Generates synthetic, referentially-consistent data for the customer_platform demo.

Writes CSVs to ./output/ so the data can be inspected before it ever touches a
database. Run load_to_postgres.py afterwards to load these into Neon.

Usage:
    python generate_data.py [--seed N]
"""
import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from faker import Faker

# Scale — see docs/decisions.md item C at the repo root.
N_CUSTOMERS = 200
N_PRODUCTS = 50
N_ORDERS = 2000
N_ORDER_ITEMS = 5000
N_SUPPORT_TICKETS = 500

OUTPUT_DIR = Path(__file__).parent / "output"

PLAN_TIERS = ["free", "pro", "enterprise"]
PLAN_WEIGHTS = [0.6, 0.3, 0.1]
ORDER_STATUSES = ["completed", "completed", "completed", "pending", "cancelled", "refunded"]
TICKET_PRIORITIES = ["low", "medium", "high"]
TICKET_STATUSES = ["open", "in_progress", "closed"]
TICKET_CATEGORIES = ["billing", "technical", "onboarding", "feature_request", "bug_report"]
PRODUCT_CATEGORIES = ["software", "hardware", "services", "add_on", "support_plan"]

EARLIEST_SIGNUP = datetime(2022, 1, 1)
NOW = datetime(2026, 9, 8)  # keep generated data internally consistent regardless of wall-clock run date


def generate_customers(fake: Faker, n: int) -> pd.DataFrame:
    rows = []
    for customer_id in range(1, n + 1):
        signup_date = fake.date_time_between(start_date=EARLIEST_SIGNUP, end_date=NOW)
        status = random.choices(["active", "churned"], weights=[0.85, 0.15])[0]
        rows.append({
            "customer_id": customer_id,
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "email": fake.unique.email(),
            "phone": fake.phone_number(),
            "company": fake.company(),
            "country": fake.country(),
            "plan_tier": random.choices(PLAN_TIERS, weights=PLAN_WEIGHTS)[0],
            "status": status,
            "signup_date": signup_date.date().isoformat(),
            "created_at": signup_date.isoformat(sep=" "),
            "updated_at": fake.date_time_between(start_date=signup_date, end_date=NOW).isoformat(sep=" "),
        })
    return pd.DataFrame(rows)


def generate_products(fake: Faker, n: int) -> pd.DataFrame:
    rows = []
    for product_id in range(1, n + 1):
        rows.append({
            "product_id": product_id,
            "product_name": fake.catch_phrase(),
            "category": random.choice(PRODUCT_CATEGORIES),
            "unit_price": round(random.uniform(9.99, 999.99), 2),
            "created_at": fake.date_time_between(start_date=EARLIEST_SIGNUP, end_date=NOW).isoformat(sep=" "),
        })
    return pd.DataFrame(rows)


def generate_orders(fake: Faker, n: int, customers: pd.DataFrame) -> pd.DataFrame:
    rows = []
    customer_signup = dict(zip(customers["customer_id"], customers["created_at"]))
    for order_id in range(1, n + 1):
        customer_id = random.choice(customers["customer_id"].tolist())
        earliest = datetime.fromisoformat(customer_signup[customer_id])
        order_date = fake.date_time_between(start_date=earliest, end_date=NOW)
        rows.append({
            "order_id": order_id,
            "customer_id": customer_id,
            "order_date": order_date.isoformat(sep=" "),
            "status": random.choice(ORDER_STATUSES),
            "order_total": 0.0,  # filled in after order_items are generated
            "created_at": order_date.isoformat(sep=" "),
            "updated_at": fake.date_time_between(start_date=order_date, end_date=NOW).isoformat(sep=" "),
        })
    return pd.DataFrame(rows)


def generate_order_items(n: int, orders: pd.DataFrame, products: pd.DataFrame) -> pd.DataFrame:
    order_ids = orders["order_id"].tolist()
    product_price = dict(zip(products["product_id"], products["unit_price"]))
    product_ids = products["product_id"].tolist()

    # Guarantee every order has at least one item, then top up to N randomly.
    assignments = list(order_ids)
    while len(assignments) < n:
        assignments.append(random.choice(order_ids))
    assignments = assignments[:n]
    random.shuffle(assignments)

    rows = []
    for order_item_id, order_id in enumerate(assignments, start=1):
        product_id = random.choice(product_ids)
        quantity = random.randint(1, 5)
        unit_price = product_price[product_id]
        line_total = round(quantity * unit_price, 2)
        rows.append({
            "order_item_id": order_item_id,
            "order_id": order_id,
            "product_id": product_id,
            "quantity": quantity,
            "unit_price": unit_price,
            "line_total": line_total,
        })
    return pd.DataFrame(rows)


def generate_support_tickets(fake: Faker, n: int, customers: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    customer_orders = orders.groupby("customer_id")["order_id"].apply(list).to_dict()
    customer_signup = dict(zip(customers["customer_id"], customers["created_at"]))
    customer_ids = customers["customer_id"].tolist()

    rows = []
    for ticket_id in range(1, n + 1):
        customer_id = random.choice(customer_ids)
        earliest = datetime.fromisoformat(customer_signup[customer_id])
        created_at = fake.date_time_between(start_date=earliest, end_date=NOW)
        status = random.choices(TICKET_STATUSES, weights=[0.2, 0.15, 0.65])[0]
        resolved_at = None
        csat_score = None
        if status == "closed":
            resolved_at = fake.date_time_between(start_date=created_at, end_date=NOW)
            csat_score = random.choices([1, 2, 3, 4, 5], weights=[0.05, 0.05, 0.15, 0.35, 0.4])[0]

        related_orders = customer_orders.get(customer_id, [])
        order_id = random.choice(related_orders) if related_orders and random.random() < 0.4 else None

        rows.append({
            "ticket_id": ticket_id,
            "customer_id": customer_id,
            "order_id": order_id,
            "priority": random.choices(TICKET_PRIORITIES, weights=[0.5, 0.35, 0.15])[0],
            "status": status,
            "category": random.choice(TICKET_CATEGORIES),
            "csat_score": csat_score,
            "created_at": created_at.isoformat(sep=" "),
            "resolved_at": resolved_at.isoformat(sep=" ") if resolved_at else None,
        })
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducible output")
    parser.add_argument("--customers", type=int, default=N_CUSTOMERS)
    parser.add_argument("--products", type=int, default=N_PRODUCTS)
    parser.add_argument("--orders", type=int, default=N_ORDERS)
    parser.add_argument("--order-items", type=int, default=N_ORDER_ITEMS)
    parser.add_argument("--support-tickets", type=int, default=N_SUPPORT_TICKETS)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR,
                         help="Defaults to ./output -- use a different dir for scale benchmarks so the demo dataset isn't overwritten")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)
        Faker.seed(args.seed)

    fake = Faker()
    output_dir = args.output_dir
    output_dir.mkdir(exist_ok=True, parents=True)

    customers = generate_customers(fake, args.customers)
    products = generate_products(fake, args.products)
    orders = generate_orders(fake, args.orders, customers)
    order_items = generate_order_items(args.order_items, orders, products)

    order_totals = order_items.groupby("order_id")["line_total"].sum().round(2)
    orders["order_total"] = orders["order_id"].map(order_totals).fillna(0.0)

    support_tickets = generate_support_tickets(fake, args.support_tickets, customers, orders)

    customers.to_csv(output_dir / "customers.csv", index=False)
    products.to_csv(output_dir / "products.csv", index=False)
    orders.to_csv(output_dir / "orders.csv", index=False)
    order_items.to_csv(output_dir / "order_items.csv", index=False)
    support_tickets.to_csv(output_dir / "support_tickets.csv", index=False)

    print(f"Wrote {len(customers)} customers, {len(products)} products, {len(orders)} orders, "
          f"{len(order_items)} order_items, {len(support_tickets)} support_tickets to {output_dir}")


if __name__ == "__main__":
    main()
