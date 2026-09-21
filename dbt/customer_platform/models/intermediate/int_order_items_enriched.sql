with order_items as (
    select * from {{ ref('stg_order_items') }}
),

products as (
    select * from {{ ref('stg_products') }}
),

enriched as (
    select
        order_items.order_item_id,
        order_items.order_id,
        order_items.product_id,
        products.product_name,
        products.category                                       as product_category,
        order_items.quantity,
        order_items.unit_price,
        order_items.line_total,
        products.unit_price                                     as catalog_unit_price,
        round(order_items.unit_price - products.unit_price, 2)   as price_variance
    from order_items
    left join products on order_items.product_id = products.product_id
)

select * from enriched
