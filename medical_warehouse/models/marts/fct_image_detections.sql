-- models/marts/fct_image_detections.sql
--
-- FCT_IMAGE_DETECTIONS: one row per detected object per image
-- Joins YOLO detection results with fct_messages and dim_channels
-- so analysts can answer questions like:
--   "Do promotional posts get more views?"
--   "Which channels use more visual content?"

with detections as (
    -- Pull raw YOLO results from PostgreSQL
    select * from raw.yolo_detections
),

messages as (
    select
        message_id,
        channel_key,
        date_key,
        views,
        forwards
    from {{ ref('fct_messages') }}
),

channels as (
    select channel_key, channel_name, channel_type
    from {{ ref('dim_channels') }}
)

select
    -- Cast message_id to integer to match fct_messages
    cast(d.message_id as integer)   as message_id,

    -- Foreign keys to dimensions
    m.channel_key,
    m.date_key,

    -- Detection details from YOLO
    d.detected_class,
    d.confidence_score,
    d.image_category,
    d.image_path,

    -- Bring in channel context
    c.channel_name,
    c.channel_type,

    -- Bring in engagement metrics so we can compare
    -- promotional vs product_display views directly
    m.views,
    m.forwards

from detections d
left join messages m
    on cast(d.message_id as integer) = m.message_id
left join channels c
    on m.channel_key = c.channel_key