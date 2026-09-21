-- Local target (DuckDB, zero-cost testing) reads from a dbt seed instead of
-- the Airbyte-landed Snowflake source. See docs/local-testing.md.
with source as (
    {% if target.name == 'local' %}
    select * from {{ ref('raw_customers') }}
    {% else %}
    select * from {{ source('raw', 'customers') }}
    {% endif %}
),

renamed as (
    select
        customer_id::int          as customer_id,
        first_name,
        last_name,
        email,
        phone,
        company,
        country,
        plan_tier,
        status,
        signup_date::date         as signup_date,
        created_at::timestamp     as created_at,
        updated_at::timestamp     as updated_at
    from source
)

select * from renamed
