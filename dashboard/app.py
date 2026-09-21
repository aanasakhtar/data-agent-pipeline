"""
Streamlit dashboard reading the platinum layer from Snowflake.

Run with: streamlit run app.py
"""
import os

import pandas as pd
import plotly.express as px
import snowflake.connector
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Customer Platform Dashboard", layout="wide")


@st.cache_resource
def get_connection():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        role=os.environ["SNOWFLAKE_ROLE"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema="PLATINUM",
    )


@st.cache_data(ttl=300)
def load_table(query: str) -> pd.DataFrame:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(query)
        return cur.fetch_pandas_all()


st.title("Customer Platform Dashboard")
st.caption("Reading directly from Snowflake PLATINUM schema (customer_360, weekly_business_metrics)")

try:
    customer_360 = load_table("select * from customer_360")
    weekly_metrics = load_table("select * from weekly_business_metrics order by week_start_date")
except Exception as e:
    st.error(
        "Could not query Snowflake. Make sure SNOWFLAKE_* env vars are set and "
        "`dbt build` has populated the PLATINUM schema.\n\n"
        f"Error: {e}"
    )
    st.stop()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Customers", len(customer_360))
col2.metric("At-Risk Customers", int(customer_360["IS_CHURN_RISK"].sum()))
col3.metric("Total Lifetime Value", f"${customer_360['LIFETIME_VALUE'].sum():,.0f}")
col4.metric("Avg CSAT", f"{customer_360['AVG_CSAT_SCORE'].mean():.2f}")

st.subheader("Weekly Revenue")
st.plotly_chart(px.line(weekly_metrics, x="WEEK_START_DATE", y="REVENUE"), use_container_width=True)

col_a, col_b = st.columns(2)
with col_a:
    st.subheader("Weekly New Customers")
    st.plotly_chart(px.bar(weekly_metrics, x="WEEK_START_DATE", y="NEW_CUSTOMERS"), use_container_width=True)
with col_b:
    st.subheader("Weekly Ticket Volume & CSAT")
    st.plotly_chart(
        px.line(weekly_metrics, x="WEEK_START_DATE", y="AVG_CSAT_SCORE"),
        use_container_width=True,
    )

st.subheader("Customer 360")
st.dataframe(customer_360, use_container_width=True)
