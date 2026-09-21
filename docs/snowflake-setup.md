# Snowflake Setup (Manual — do this yourself, then report back)

## 1. Create the trial account

1. Go to https://signup.snowflake.com and sign up for the 30-day free trial.
   Any cloud provider/region is fine (pick one close to you).
2. After signup you'll land in Snowsight (the web UI) as the `ACCOUNTADMIN` role.
3. Note your **account identifier** — shown in the URL, e.g.
   `https://<account_identifier>.snowflakecomputing.com`, or under
   Admin → Accounts in Snowsight. You'll need this for dbt and Airbyte.

## 2. Run this setup SQL in a Snowsight worksheet

This creates an isolated warehouse/database/role/user for dbt and Airbyte to use,
rather than running everything as `ACCOUNTADMIN`.

```sql
-- Warehouse (compute)
CREATE WAREHOUSE IF NOT EXISTS DBT_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE;

-- Database + schemas for the medallion layers
CREATE DATABASE IF NOT EXISTS CUSTOMER_PLATFORM;
CREATE SCHEMA IF NOT EXISTS CUSTOMER_PLATFORM.RAW;       -- Airbyte lands data here
CREATE SCHEMA IF NOT EXISTS CUSTOMER_PLATFORM.BRONZE;
CREATE SCHEMA IF NOT EXISTS CUSTOMER_PLATFORM.SILVER;
CREATE SCHEMA IF NOT EXISTS CUSTOMER_PLATFORM.GOLD;
CREATE SCHEMA IF NOT EXISTS CUSTOMER_PLATFORM.PLATINUM;
CREATE SCHEMA IF NOT EXISTS CUSTOMER_PLATFORM.CI;        -- isolated schema for GitHub Actions

-- Role for dbt + Airbyte
CREATE ROLE IF NOT EXISTS DBT_ROLE;
GRANT USAGE ON WAREHOUSE DBT_WH TO ROLE DBT_ROLE;
GRANT ALL ON DATABASE CUSTOMER_PLATFORM TO ROLE DBT_ROLE;
GRANT ALL ON ALL SCHEMAS IN DATABASE CUSTOMER_PLATFORM TO ROLE DBT_ROLE;
GRANT ALL ON FUTURE SCHEMAS IN DATABASE CUSTOMER_PLATFORM TO ROLE DBT_ROLE;
GRANT ALL ON ALL TABLES IN DATABASE CUSTOMER_PLATFORM TO ROLE DBT_ROLE;
GRANT ALL ON FUTURE TABLES IN DATABASE CUSTOMER_PLATFORM TO ROLE DBT_ROLE;

-- Dedicated user (used by both dbt locally/CI and Airbyte's destination config)
CREATE USER IF NOT EXISTS DBT_USER
  PASSWORD = '<choose a strong password>'
  DEFAULT_ROLE = DBT_ROLE
  DEFAULT_WAREHOUSE = DBT_WH
  MUST_CHANGE_PASSWORD = FALSE;

GRANT ROLE DBT_ROLE TO USER DBT_USER;
```

Replace `<choose a strong password>` before running. Consider a separate Airbyte-only
user (`AIRBYTE_LOADER`) with write access to `RAW` only, if you want tighter separation
later — for this hands-on build, sharing `DBT_USER`/`DBT_ROLE` for both is simpler and fine.

## What to hand back to Claude

- Account identifier
- `SNOWFLAKE_USER` = `DBT_USER`, `SNOWFLAKE_PASSWORD` = the password you set
- `SNOWFLAKE_ROLE` = `DBT_ROLE`
- `SNOWFLAKE_WAREHOUSE` = `DBT_WH`
- `SNOWFLAKE_DATABASE` = `CUSTOMER_PLATFORM`

Put these into your local `.env` (never commit it) and later into GitHub Actions Secrets
with the same names for CI.
