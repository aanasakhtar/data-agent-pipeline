with source as (
    {% if target.name == 'local' %}
    select * from {{ ref('raw_order_items') }}
    {% else %}
    select * from {{ source('raw', 'order_items') }}
    {% endif %}
),

renamed as (
    select
        order_item_id::int        as order_item_id,
        order_id::int              as order_id,
        product_id::int            as product_id,
        quantity::int               as quantity,
        unit_price::numeric(10,2) as unit_price,
        line_total::numeric(10,2) as line_total
    from source
)

select * from renamed
