with source as (
    {% if target.name == 'local' %}
    select * from {{ ref('raw_orders') }}
    {% else %}
    select * from {{ source('raw', 'orders') }}
    {% endif %}
),

renamed as (
    select
        order_id::int              as order_id,
        customer_id::int           as customer_id,
        order_date::timestamp      as order_date,
        status                     as order_status,
        order_total::numeric(10,2) as order_total,
        created_at::timestamp      as created_at,
        updated_at::timestamp      as updated_at
    from source
)

select * from renamed
