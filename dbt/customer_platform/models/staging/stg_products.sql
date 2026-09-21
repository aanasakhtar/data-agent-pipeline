with source as (
    {% if target.name == 'local' %}
    select * from {{ ref('raw_products') }}
    {% else %}
    select * from {{ source('raw', 'products') }}
    {% endif %}
),

renamed as (
    select
        product_id::int           as product_id,
        product_name,
        category,
        unit_price::numeric(10,2) as unit_price,
        created_at::timestamp     as created_at
    from source
)

select * from renamed
