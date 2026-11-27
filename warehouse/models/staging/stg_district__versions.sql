-- Every landed version of `district`, typed and cleaned. One row per key per extract.
select
    {{ clean_code('district_code') }} as district_code,
    {{ clean_code('province_code') }} as province_code,
    {{ clean_text('district_name') }} as district_name,
    cast(created_at as timestamp) as created_at,
    cast(updated_at as timestamp) as updated_at,
    cast(_load_date as date) as _load_date
from {{ landed('district') }}
