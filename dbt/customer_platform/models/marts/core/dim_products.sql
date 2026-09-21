select
    product_id,
    product_name,
    category as product_category,
    unit_price,
    created_at
from {{ ref('stg_products') }}
