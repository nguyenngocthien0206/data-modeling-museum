-- Every landed version of `membership_tier`, typed and cleaned. One row per key per extract.
select
    {{ clean_code('tier_code') }} as tier_code,
    {{ clean_text('tier_name') }} as tier_name,
    cast(rank as integer) as rank,
    cast(min_spend_12m as bigint) as min_spend_12m,
    cast(created_at as timestamp) as created_at,
    cast(updated_at as timestamp) as updated_at,
    cast(_load_date as date) as _load_date
from {{ landed('membership_tier') }}
