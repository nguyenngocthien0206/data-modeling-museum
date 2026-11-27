-- Every landed version of `province`, typed and cleaned. One row per key per extract.
select
    {{ clean_code('province_code') }} as province_code,
    {{ clean_text('province_name') }} as province_name,
    cast(created_at as timestamp) as created_at,
    cast(updated_at as timestamp) as updated_at,
    cast(_load_date as date) as _load_date
from {{ landed('province') }}
