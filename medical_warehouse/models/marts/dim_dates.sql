-- models/marts/dim_dates.sql
--
-- DIM_DATES: one row per unique date that appears in our messages
-- This lets analysts easily filter/group by day, week, month, quarter
-- without doing date math every time in their queries

with date_spine as (
    -- Get every unique date from our messages
    select distinct
        cast(message_date as date) as full_date
    from {{ ref('stg_telegram_messages') }}
)

select
    -- Date key as integer: e.g. 20260624 (easy to join on)
    cast(to_char(full_date, 'YYYYMMDD') as integer)     as date_key,

    full_date,

    -- Day of week: 1=Sunday, 7=Saturday (PostgreSQL convention)
    extract(dow from full_date) + 1                      as day_of_week,

    -- Human-readable day name
    to_char(full_date, 'Day')                            as day_name,

    extract(week from full_date)                         as week_of_year,
    extract(month from full_date)                        as month,
    to_char(full_date, 'Month')                          as month_name,
    extract(quarter from full_date)                      as quarter,
    extract(year from full_date)                         as year,

    -- Weekend flag: Sunday=0, Saturday=6 in PostgreSQL extract(dow)
    case
        when extract(dow from full_date) in (0, 6) then true
        else false
    end                                                  as is_weekend

from date_spine
order by full_date