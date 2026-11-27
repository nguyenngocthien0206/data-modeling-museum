-- Every landed version of `channel`, typed and cleaned. One row per key per extract.
select
    {{ clean_code('channel_code') }} as channel_code,
    {{ clean_text('channel_name') }} as channel_name,
    cast(created_at as timestamp) as created_at,
    cast(updated_at as timestamp) as updated_at,
    cast(_load_date as date) as _load_date
from {{ landed('channel') }}
