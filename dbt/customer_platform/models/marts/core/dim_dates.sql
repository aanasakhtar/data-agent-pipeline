with spine as (
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('2022-01-01' as date)",
        end_date="cast('2026-12-31' as date)"
    ) }}
)

select
    date_day,
    extract(year from date_day)        as year,
    extract(month from date_day)       as month,
    extract(week from date_day)        as iso_week,
    extract(dayofweek from date_day)   as day_of_week,
    date_trunc('week', date_day)       as week_start_date
from spine
