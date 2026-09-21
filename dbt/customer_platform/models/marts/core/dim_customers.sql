with snapshot as (
    select * from {{ ref('customers_snapshot') }}
    where dbt_valid_to is null
)

select
    customer_id,
    first_name,
    last_name,
    email,
    phone,
    company,
    country,
    plan_tier,
    status          as customer_status,
    signup_date,
    dbt_valid_from  as plan_status_effective_from
from snapshot
