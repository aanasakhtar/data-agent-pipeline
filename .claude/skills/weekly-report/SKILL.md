---
name: weekly-report
description: Refreshes weekly_business_metrics and customer_360, then produces a short narrative summary of the latest week (revenue, new customers, ticket volume, CSAT, churn-risk customers). Use when the user asks for a weekly report, business summary, or analytics update on this pipeline's data.
---

# Weekly Report

This is the concrete analog of the "automated analytics reports" piece of the
original architecture (see `docs/architecture.md`) — reading the platinum layer
and turning it into a human-readable summary, rather than a customer having to
query Snowflake themselves.

## Steps

1. Make sure the platinum models are current:
   ```
   cd dbt/customer_platform
   dbt build --select customer_360 weekly_business_metrics+
   ```

2. Query the latest week's row from `PLATINUM.weekly_business_metrics` and the
   most recent 4-8 weeks for trend context. Use the Snowflake credentials from
   `.env` (same ones the dashboard uses) — either via `snowsql`/a short Python
   script with `snowflake-connector-python`, or by asking the user to run a
   query if no CLI is available.

3. Also pull `PLATINUM.customer_360` filtered to `IS_CHURN_RISK = true`, to
   name specific at-risk customers in the summary (not just an aggregate count).

4. Write a short narrative summary covering:
   - Revenue this week vs. the trailing average, and the direction of the trend
   - New customers signed up this week
   - Ticket volume and average CSAT, flagged if CSAT dropped notably
   - Named list of at-risk customers (from `customer_360`) worth a human follow-up

5. Offer to also launch the dashboard (`streamlit run dashboard/app.py`) if the
   user wants to explore interactively rather than just read the summary.

Keep the summary to a few short paragraphs or a bulleted list — this is meant to
be skimmed, not a full report document, unless the user asks for more detail.
