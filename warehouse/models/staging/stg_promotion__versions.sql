-- Every landed version of `promotion`, typed and cleaned. One row per key per extract.
select
    cast(promotion_id as bigint) as promotion_id,
    {{ clean_code('promo_code') }} as promo_code,
    {{ clean_text('promo_name') }} as promo_name,
    {{ clean_code('promo_type') }} as promo_type,
    cast(promo_value as bigint) as promo_value,
    cast(starts_on as date) as starts_on,
    cast(ends_on as date) as ends_on,
    cast(created_at as timestamp) as created_at,
    cast(updated_at as timestamp) as updated_at,
    cast(_load_date as date) as _load_date
from {{ landed('promotion') }}
