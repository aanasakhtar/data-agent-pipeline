select
    ticket_id,
    customer_id,
    order_id,
    priority,
    ticket_status,
    category,
    csat_score,
    created_at,
    resolved_at,
    datediff('hour', created_at, resolved_at) as resolution_hours
from {{ ref('stg_support_tickets') }}
