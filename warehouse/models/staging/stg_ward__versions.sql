-- Every landed version of `ward`, typed and cleaned. One row per key per extract.
select
    {{ clean_code('ward_code') }} as ward_code,
    {{ clean_code('district_code') }} as district_code,
    {{ clean_text('ward_name') }} as ward_name,
    cast(created_at as timestamp) as created_at,
    cast(updated_at as timestamp) as updated_at,
    cast(_load_date as date) as _load_date
from {{ landed('ward') }}
