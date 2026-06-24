-- models/marts/fct_messages.sql
--
-- FCT_MESSAGES: the central fact table in our star schema
-- Each row = one Telegram message
-- It connects to dimensions via foreign keys (channel_key, date_key)
-- This is what analysts query most — it has all the measurable facts:
--   views, forwards, message_length, has_image

with messages as (
    select * from {{ ref('stg_telegram_messages') }}
),

channels as (
    select * from {{ ref('dim_channels') }}
),

dates as (
    select * from {{ ref('dim_dates') }}
)

select
    -- Primary key
    m.message_id,

    -- Foreign keys linking to dimension tables
    c.channel_key,
    d.date_key,

    -- Message content
    m.message_text,
    m.message_length,

    -- Measurable facts (the numbers we analyze)
    m.views,
    m.forwards,
    m.has_image,
    m.image_path,

    -- Keep the full timestamp for time-series analysis
    m.message_date

from messages m
left join channels c
    on m.channel_name = c.channel_name
left join dates d
    on cast(m.message_date as date) = d.full_date