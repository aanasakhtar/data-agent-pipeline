with orders as (
    select * from {{ ref('stg_orders') }}
),

item_agg as (
    select
        order_id,
        count(*)      as item_count,
        sum(quantity) as total_quantity
    from {{ ref('int_order_items_enriched') }}
    group by 1
)

select
    orders.order_id,
    orders.customer_id,
    orders.order_date,
    date_trunc('day', orders.order_date)   as order_date_day,
    orders.order_status,
    orders.order_total,
    coalesce(item_agg.item_count, 0)       as item_count,
    coalesce(item_agg.total_quantity, 0)   as total_quantity
from orders
left join item_agg on orders.order_id = item_agg.order_id
