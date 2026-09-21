"""
Loads the CSVs from ./output/ (produced by generate_data.py) into a Postgres
database (Neon) via DATABASE_URL. Creates the schema first if it doesn't exist.

Usage:
    export DATABASE_URL=postgresql://user:pass@host/db?sslmode=require
    python load_to_postgres.py [--truncate]
"""
import argparse
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

OUTPUT_DIR = Path(__file__).parent / "output"
SCHEMA_SQL_PATH = Path(__file__).parent.parent / "schema.sql"

# Load order matters: children after the parents they reference.
TABLE_LOAD_ORDER = ["customers", "products", "orders", "order_items", "support_tickets"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--truncate", action="store_true",
                         help="Truncate existing tables before loading (default: append)")
    args = parser.parse_args()

    load_dotenv()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is not set. Export it or put it in a .env file.")

    engine = create_engine(database_url)

    with engine.begin() as conn:
        print("Applying schema.sql ...")
        conn.execute(text(SCHEMA_SQL_PATH.read_text()))

        if args.truncate:
            print("Truncating existing tables ...")
            conn.execute(text(
                f"TRUNCATE TABLE {', '.join(reversed(TABLE_LOAD_ORDER))} RESTART IDENTITY CASCADE"
            ))

        for table in TABLE_LOAD_ORDER:
            csv_path = OUTPUT_DIR / f"{table}.csv"
            if not csv_path.exists():
                raise SystemExit(f"Missing {csv_path} — run generate_data.py first.")
            df = pd.read_csv(csv_path)
            df.to_sql(table, conn, if_exists="append", index=False, method="multi", chunksize=500)
            print(f"Loaded {len(df)} rows into {table}")

    print("Done.")


if __name__ == "__main__":
    main()
