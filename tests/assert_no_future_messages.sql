-- tests/assert_no_future_messages.sql
--
-- Custom test: ensures no messages have a future date
-- dbt tests PASS when this query returns 0 rows
-- If any future-dated messages exist, this returns rows and the test FAILS

select *
from {{ ref('stg_telegram_messages') }}
where message_date > now()