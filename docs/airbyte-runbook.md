# Airbyte Cloud Runbook (Manual — do this yourself, then report back)

Prerequisite: Neon source DB is loaded (`docs/neon-setup.md`) and Snowflake is set up
(`docs/snowflake-setup.md`).

## 1. Sign up

Go to https://airbyte.com/product/airbyte-cloud and create an account (free tier is
enough for this volume of data).

## 2. Create the Source (Neon Postgres)

1. Sources → New source → search "Postgres".
2. Fill in:
   - Host: from your Neon connection string (the part after `@`, before `/neondb`)
   - Port: `5432`
   - Database name: `neondb` (or whatever Neon named it)
   - Username / Password: from the Neon connection string
   - SSL Mode: `require`
   - Replication method: **Standard (xmin)** or **Scan Changes with User Defined Cursor**
     — either works for a first pass since we're doing Full Refresh; incremental CDC
     (logical replication) is a good later exercise.
3. Test the connection, then save.

## 3. Create the Destination (Snowflake)

1. Destinations → New destination → search "Snowflake".
2. Fill in the values from `docs/snowflake-setup.md`:
   - Host: `<account_identifier>.snowflakecomputing.com`
   - Role: `DBT_ROLE`
   - Warehouse: `DBT_WH`
   - Database: `CUSTOMER_PLATFORM`
   - Default Schema: `RAW`
   - Username / Password: `DBT_USER` / the password you set
3. Test the connection, then save.

## 4. Create the Connection

1. Connections → New connection → select the Postgres source and Snowflake destination.
2. Select all 5 streams: `customers`, `products`, `orders`, `order_items`, `support_tickets`.
3. Sync mode: **Full Refresh | Overwrite** for each stream (simplest for this first pass).
4. Schedule: Manual, or a low frequency (e.g. every 24h) — no need for real-time for a demo.
5. Save, then click **Sync now** to run the first sync.
6. Wait for it to complete and show a green "Succeeded" status with a row count per stream.

## What to hand back to Claude

After the first successful sync, go to Snowflake (Snowsight) and run:

```sql
SHOW TABLES IN SCHEMA CUSTOMER_PLATFORM.RAW;
```

Report back:
- The exact table names Airbyte created (Airbyte often lowercases and may prefix names —
  e.g. `customers` vs `raw_customers` vs `_airbyte_raw_customers` depending on the
  destination's normalization settings).
- The row counts per stream shown in the Airbyte sync summary (should roughly match
  `docs/decisions.md` item C: ~200 customers, ~50 products, ~2,000 orders, ~5,000
  order_items, ~500 support_tickets).

Claude will use this to finalize `dbt/customer_platform/models/staging/_staging__sources.yml`,
which currently has placeholder table names.
