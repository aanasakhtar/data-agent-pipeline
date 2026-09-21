{% snapshot customers_snapshot %}

{{
    config(
        target_schema='silver',
        unique_key='customer_id',
        strategy='check',
        check_cols=['plan_tier', 'status'],
    )
}}

select * from {{ ref('stg_customers') }}

{% endsnapshot %}
