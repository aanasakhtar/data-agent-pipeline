with customers as (
    select * from {{ ref('dim_customers') }}
),

orders as (
    select * from {{ ref('fct_orders') }}
    where order_status = 'completed'
),

order_agg as (
    select
        customer_id,
        count(*)         as completed_order_count,
        sum(order_total) as lifetime_value,
        avg(order_total) as avg_order_value,
        max(order_date)  as last_order_date
    from orders
    group by 1
),

tickets as (
    select * from {{ ref('fct_support_tickets') }}
),

ticket_agg as (
    select
        customer_id,
        sum(case when ticket_status != 'closed' then 1 else 0 end) as open_ticket_count,
        avg(csat_score) as avg_csat_score
    from tickets
    group by 1
)

select
    customers.customer_id,
    customers.first_name,
    customers.last_name,
    customers.email,
    customers.company,
    customers.country,
    customers.plan_tier,
    customers.customer_status,
    customers.signup_date,
    coalesce(order_agg.completed_order_count, 0) as completed_order_count,
    coalesce(order_agg.lifetime_value, 0)         as lifetime_value,
    order_agg.avg_order_value,
    order_agg.last_order_date,
    coalesce(ticket_agg.open_ticket_count, 0)     as open_ticket_count,
    ticket_agg.avg_csat_score,
    case
        when customers.customer_status = 'churned' then true
        when coalesce(ticket_agg.open_ticket_count, 0) >= 2
             and ticket_agg.avg_csat_score < 3 then true
        else false
    end as is_churn_risk
from customers
left join order_agg on customers.customer_id = order_agg.customer_id
left join ticket_agg on customers.customer_id = ticket_agg.customer_id
