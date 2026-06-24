-- models/staging/stg_telegram_messages.sql
--
-- This is the STAGING layer. Think of it as the "cleaning station".
-- We take raw messy data from raw.telegram_messages and:
--   - Cast columns to correct types
--   - Rename columns to consistent snake_case
--   - Remove invalid records (null message_id, future dates)
--   - Add calculated fields (message_length, has_image)

with source as (
    -- Pull everything from the raw table loaded by our Python script
    select * from raw.telegram_messages
),

cleaned as (
    select
        -- Cast message_id to integer (it came in as text from JSON)
        cast(message_id as integer)         as message_id,

        -- Trim whitespace from channel name
        trim(channel_name)                  as channel_name,

        -- Cast to timestamp with timezone
        cast(message_date as timestamptz)   as message_date,

        -- Clean message text: replace nulls with empty string
        coalesce(message_text, '')          as message_text,

        -- Calculate message length (useful for analytics)
        length(coalesce(message_text, ''))  as message_length,

        -- Boolean flag for media
        cast(has_media as boolean)          as has_media,

        -- Rename has_media to has_image for clarity
        cast(has_media as boolean)          as has_image,

        -- Image path (nullable)
        image_path,

        -- Numeric fields
        cast(views as integer)              as views,
        cast(forwards as integer)           as forwards

    from source
    where
        -- Remove records with no message ID
        message_id is not null
        -- Remove records with empty channel name
        and trim(channel_name) != ''
        -- Remove future-dated messages (data quality check)
        and cast(message_date as timestamptz) <= now()
)

select * from cleaned