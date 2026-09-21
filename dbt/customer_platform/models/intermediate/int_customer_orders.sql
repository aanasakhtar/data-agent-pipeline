with orders as (
    select * from {{ ref('stg_orders') }}
),

customers as (
    select * from {{ ref('stg_customers') }}
),

joined as (
    select
        orders.order_id,
        orders.customer_id,
        orders.order_date,
        orders.order_status,
        orders.order_total,
        customers.plan_tier,
        customers.status                                      as customer_status,
        customers.signup_date,
        datediff('day', customers.signup_date, orders.order_date) as days_since_signup,
        row_number() over (
            partition by orders.customer_id order by orders.order_date
        )                                                      as customer_order_sequence
    from orders
    left join customers on orders.customer_id = customers.customer_id
)

select * from joined
