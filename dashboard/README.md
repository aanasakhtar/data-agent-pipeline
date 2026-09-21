# Dashboard

Streamlit app reading the platinum layer (`PLATINUM.customer_360`,
`PLATINUM.weekly_business_metrics`) directly from Snowflake. This is the
"auto-built dashboard" piece of the pipeline, in its simplest possible form --
no separate BI account needed.

## Run

```
pip install -r requirements.txt
export SNOWFLAKE_ACCOUNT=... SNOWFLAKE_USER=... SNOWFLAKE_PASSWORD=... \
       SNOWFLAKE_ROLE=... SNOWFLAKE_WAREHOUSE=... SNOWFLAKE_DATABASE=...
streamlit run app.py
```

(Or put those in a `.env` at the repo root -- `app.py` loads it automatically.)

Requires `dbt build` to have already populated the `PLATINUM` schema.
