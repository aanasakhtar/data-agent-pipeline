# Customer Data Platform — Hands-On Build

A working, real-infrastructure recreation of a customer-onboarding data platform:
Airbyte pulls a customer's source data into Snowflake, dbt builds it up through
Bronze → Silver → Gold → Platinum layers, a dashboard reads the top layer, and
GitHub Actions gates changes with automated tests. See [`workflow.md`](workflow.md)
for the original design spec this is built from, and [`docs/architecture.md`](docs/architecture.md)
for how each piece below maps onto it.

Source data is synthetic (no real customer), but every other component is real:
a real Postgres source (Neon), a real warehouse (Snowflake), a real Airbyte Cloud
connector, and real CI.

## Layout

| Path | What it is |
| --- | --- |
| `data-source/` | Synthetic "customer source system" — schema + generator that seeds a Postgres DB, which Airbyte treats exactly like a real customer's database. |
| `dbt/customer_platform/` | The transformation pipeline: staging (bronze), intermediate + snapshots (silver), marts/core (gold), marts/platinum (platinum). |
| `.github/workflows/dbt_ci.yml` | CI gate — runs `dbt build` against a Snowflake CI schema on every PR. |
| `dashboard/` | Streamlit app reading the platinum layer. |
| `.claude/skills/` | Claude Code skills that wrap recurring operations (onboarding new data, weekly reporting). |
| `docs/` | Setup runbooks for the three external accounts (Neon, Snowflake, Airbyte Cloud) and a decisions log. |

## Quickstart

1. **Generate synthetic data locally** (no accounts needed yet):
   ```
   cd data-source/generator
   pip install -r requirements.txt
   python generate_data.py
   ```
   This writes CSVs to `data-source/generator/output/` so you can inspect the data
   before anything touches a real database.

2. **Stand up the source database.** Follow [`docs/neon-setup.md`](docs/neon-setup.md),
   then load the generated data:
   ```
   export DATABASE_URL=<your neon connection string>
   python load_to_postgres.py
   ```

3. **Stand up the warehouse.** Follow [`docs/snowflake-setup.md`](docs/snowflake-setup.md).

4. **Wire up ingestion.** Follow [`docs/airbyte-runbook.md`](docs/airbyte-runbook.md) to
   connect the Neon source to the Snowflake destination and run the first sync.

5. **Run the transformations:**
   ```
   cd dbt/customer_platform
   pip install dbt-snowflake
   dbt deps
   dbt build
   ```

6. **View the results:**
   ```
   cd dashboard
   pip install -r requirements.txt
   streamlit run app.py
   ```

Full sequencing and what's manual vs. automated is tracked in [`docs/decisions.md`](docs/decisions.md).
