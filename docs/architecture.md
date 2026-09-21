# Architecture: workflow.md → this repo

`workflow.md` describes a gate-locked orchestrator-worker agent pipeline for data
architecture work. This repo is a concrete, runnable instance of the *system* that
pipeline would be operating on and building — the medallion warehouse, ingestion,
transformations, tests, and CI gate. Mapping:

| workflow.md concept | Concrete implementation here |
| --- | --- |
| User Entry Point / Orchestrator | You + Claude Code, driving this repo directly |
| Phase 0: Schema Drift Check | `dbt source freshness` / comparing Neon schema to `_staging__sources.yml` |
| Phase 1: Source Exploration | Inspecting `data-source/schema.sql` and the generated CSVs before loading |
| Phase 2: System Mapping | `models/staging/` (bronze) — column-level mapping from raw Airbyte tables |
| Phase 3: Journey/Domain Design | `models/intermediate/` + `snapshots/` (silver) — SCD2, entity relationships |
| Phase 4: Master Blueprint | `models/marts/core/` (gold) — conformed dimensions and facts |
| Phase 4.5: Read-only dry-run validation | `dbt build --target ci` in `.github/workflows/dbt_ci.yml`, against an isolated CI schema |
| Plan Approval Gate | GitHub PR review + required passing CI check before merge |
| Phase 5: Implementation | `dbt run` writing real tables/views into Snowflake |
| Phase 5.5: Post-Build Validation | dbt tests (`not_null`, `unique`, `relationships`, `accepted_values`) run as part of `dbt build` |
| Platinum / reporting layer | `models/marts/platinum/` + `dashboard/app.py` + the `weekly-report` Claude Skill |
| Claude Skills (onboarding automation) | `.claude/skills/new-customer-onboarding/`, `.claude/skills/weekly-report/` |

`gate-hook.py` — the hard, out-of-band enforcement layer that blocks file writes until
explicit approval — is **not** reimplemented here. The practical substitute is: work
happens on branches, PRs require a green `dbt_ci.yml` run, and merging to `main` is the
approval gate. Building an actual Claude Code hook that mirrors `gate-hook.py` is a
reasonable next step once this base pipeline is working end-to-end (see `docs/decisions.md`, item I).

## Data flow

```
Neon (Postgres)              Airbyte Cloud                Snowflake (RAW schema)
  customers        ─────┐
  products          ────┼──── sync (Full Refresh) ───▶  RAW.customers
  orders            ────┤                                RAW.products
  order_items       ────┤                                RAW.orders
  support_tickets   ────┘                                RAW.order_items
                                                            RAW.support_tickets
                                                                  │
                                                                  ▼  dbt (models/staging)
                                                          BRONZE.stg_customers, ...
                                                                  │
                                                                  ▼  dbt (models/intermediate, snapshots)
                                                          SILVER.int_customer_orders,
                                                          SILVER.customers_snapshot, ...
                                                                  │
                                                                  ▼  dbt (models/marts/core)
                                                          GOLD.dim_customers, GOLD.fct_orders, ...
                                                                  │
                                                                  ▼  dbt (models/marts/platinum)
                                                          PLATINUM.customer_360,
                                                          PLATINUM.weekly_business_metrics
                                                                  │
                                                                  ▼
                                                          dashboard/app.py (Streamlit)
```
