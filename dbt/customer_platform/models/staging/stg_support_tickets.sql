with source as (
    {% if target.name == 'local' %}
    select * from {{ ref('raw_support_tickets') }}
    {% else %}
    select * from {{ source('raw', 'support_tickets') }}
    {% endif %}
),

renamed as (
    select
        ticket_id::int          as ticket_id,
        customer_id::int        as customer_id,
        order_id::int           as order_id,
        priority,
        status                  as ticket_status,
        category,
        csat_score::int         as csat_score,
        created_at::timestamp   as created_at,
        resolved_at::timestamp  as resolved_at
    from source
)

select * from renamed
