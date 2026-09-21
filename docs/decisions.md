# Decisions Log

Defaults chosen while scaffolding this project, so nothing is silently assumed.
Change any of these later — nothing here is load-bearing on the others.

| # | Decision | Choice | Why |
| --- | --- | --- | --- |
| A | Where the synthetic "customer source" DB lives | **Neon** (free serverless Postgres) | Airbyte Cloud can't reach `localhost`; Docker isn't installed locally. Neon gives a real, publicly reachable Postgres with no credit card. |
| B | dbt project name | `customer_platform` | Neutral, descriptive. |
| C | Synthetic data scale | ~200 customers, ~50 products, ~2,000 orders, ~5,000 order_items, ~500 support_tickets | Enough relational depth for joins/SCD2/rollups to be meaningful; small enough to sync fast and stay inside free tiers. |
| D | Source table count | 5 tables: customers, products, orders, order_items, support_tickets | `products` included so `order_items` has real per-line pricing to roll up into gold/platinum metrics. |
| E | SCD2 mechanism | dbt native `snapshot` | Idiomatic dbt pattern for slowly changing dimensions; avoids hand-rolled window-function logic. |
| F | Schema naming in Snowflake | Custom `generate_schema_name.sql` macro | Without it, dbt concatenates `<target_schema>_<custom_schema>`; the macro forces literal `BRONZE`/`SILVER`/`GOLD`/`PLATINUM` schema names to match the medallion architecture cleanly. |
| G | Dashboard tool | Streamlit | Zero new account signups, reads Snowflake directly, runs with one command. |
| H | Airbyte sync mode (first pass) | Full Refresh \| Overwrite | Simplest to verify end-to-end; Incremental sync is a good follow-up exercise once the base pipeline works. |
| I | `gate-hook.py` hard-gate enforcement from `workflow.md` | **Not built in this pass** | PR review + a required green `dbt build` CI check are the practical stand-in for now. Flagged as a natural follow-up once the base pipeline runs end-to-end. |

## Status of external accounts

- [ ] Neon project created, connection string obtained
- [ ] Synthetic data loaded into Neon
- [ ] Snowflake trial created, setup SQL run
- [ ] Airbyte Cloud account created, source/destination/connection configured, first sync run
- [ ] `dbt build` green against real Snowflake data
- [ ] GitHub remote connected, secrets added, CI passing on a PR
