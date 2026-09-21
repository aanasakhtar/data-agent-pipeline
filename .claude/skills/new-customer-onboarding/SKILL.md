---
name: new-customer-onboarding
description: Regenerates a fresh batch of synthetic customer/order/ticket data, reloads it into the Neon source database, and rebuilds the affected dbt models. Use when the user asks to onboard a new customer, refresh the demo dataset, or simulate new activity in this pipeline.
---

# New Customer Onboarding (synthetic-data refresh)

In the real system this describes (see `docs/architecture.md`), onboarding a new
customer means: connect Airbyte to their source system, run the pipeline end to
end, and hand back a working blueprint + dashboard. This repo simulates that with
synthetic data, so "onboarding" here means generating a fresh batch of realistic
data and pushing it through the same real pipeline.

## Steps

1. Confirm with the user whether this is a **full refresh** (regenerate all data,
   `--truncate` reload) or an **incremental batch** (append new rows only — note:
   `generate_data.py` currently always regenerates the full dataset; for a true
   incremental batch, either re-run with different `--seed` values and load with
   `load_to_postgres.py` without `--truncate`, or extend the generator to support
   an `--append N` mode if the user wants that — ask before building it).

2. Run the generator:
   ```
   cd data-source/generator
   python generate_data.py [--seed N]
   ```
   Show the user the row counts it prints.

3. Load into Neon (requires `DATABASE_URL` to be set — check `.env` or ask the user):
   ```
   python load_to_postgres.py [--truncate]
   ```

4. Remind the user: in the real system this is where Airbyte's sync would fire
   automatically. In this demo, they need to either trigger a manual sync in the
   Airbyte Cloud UI, or (if `AIRBYTE_CLOUD_API_TOKEN` and `AIRBYTE_CONNECTION_ID`
   are set in `.env`) offer to trigger it via the Airbyte API:
   ```
   curl -X POST https://api.airbyte.com/v1/jobs \
     -H "Authorization: Bearer $AIRBYTE_CLOUD_API_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"connectionId": "'$AIRBYTE_CONNECTION_ID'", "jobType": "sync"}'
   ```
   Do not run this without the user's confirmation — it touches external, shared
   infrastructure (a real Airbyte Cloud sync job).

5. Once the sync has landed in Snowflake's `RAW` schema, rebuild the pipeline:
   ```
   cd dbt/customer_platform
   dbt build
   ```

6. Summarize what changed: row counts before/after, any test failures, and
   whether `customer_360` / `weekly_business_metrics` look sane (spot-check a
   few rows).
