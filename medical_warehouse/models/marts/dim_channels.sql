-- models/marts/dim_channels.sql
--
-- DIM_CHANNELS: one row per Telegram channel
-- This dimension tells us ABOUT each channel:
--   what type it is, when it started, how active it is
-- The surrogate key (channel_key) is a simple integer we generate
-- so fact tables don't have to store long text channel names

with channel_stats as (
    select
        channel_name,

        -- Classify channel type based on name
        case
            when lower(channel_name) like '%pharma%'    then 'Pharmaceutical'
            when lower(channel_name) like '%cosmet%'    then 'Cosmetics'
            when lower(channel_name) like '%chem%'      then 'Medical'
            else 'General Medical'
        end                                             as channel_type,

        min(message_date)                               as first_post_date,
        max(message_date)                               as last_post_date,
        count(*)                                        as total_posts,
        round(avg(views), 0)                            as avg_views

    from {{ ref('stg_telegram_messages') }}
    group by channel_name
)

select
    -- Surrogate key: a unique integer per channel
    row_number() over (order by channel_name)   as channel_key,
    channel_name,
    channel_type,
    first_post_date,
    last_post_date,
    total_posts,
    avg_views

from channel_stats