with orders as (
    select * from {{ ref('fct_orders') }}
    where order_status = 'completed'
),

order_weekly as (
    select
        date_trunc('week', order_date) as week_start_date,
        count(*)                       as order_count,
        sum(order_total)               as revenue
    from orders
    group by 1
),

customers as (
    select * from {{ ref('dim_customers') }}
),

customer_weekly as (
    select
        date_trunc('week', signup_date) as week_start_date,
        count(*)                        as new_customers
    from customers
    group by 1
),

tickets as (
    select * from {{ ref('fct_support_tickets') }}
),

ticket_weekly as (
    select
        date_trunc('week', created_at) as week_start_date,
        count(*)                       as ticket_count,
        avg(csat_score)                as avg_csat_score
    from tickets
    group by 1
),

weeks as (
    select distinct week_start_date
    from {{ ref('dim_dates') }}
    where week_start_date <= cast('{{ var("synthetic_data_as_of") }}' as date)
)

select
    weeks.week_start_date,
    coalesce(order_weekly.order_count, 0)      as order_count,
    coalesce(order_weekly.revenue, 0)          as revenue,
    coalesce(customer_weekly.new_customers, 0) as new_customers,
    coalesce(ticket_weekly.ticket_count, 0)    as ticket_count,
    ticket_weekly.avg_csat_score
from weeks
left join order_weekly on weeks.week_start_date = order_weekly.week_start_date
left join customer_weekly on weeks.week_start_date = customer_weekly.week_start_date
left join ticket_weekly on weeks.week_start_date = ticket_weekly.week_start_date
order by weeks.week_start_date
