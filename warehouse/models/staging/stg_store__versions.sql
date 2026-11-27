-- Every landed version of `store`, typed and cleaned. One row per key per extract.
select
    cast(store_id as bigint) as store_id,
    {{ clean_code('store_code') }} as store_code,
    {{ clean_text('store_name') }} as store_name,
    {{ clean_code('ward_code') }} as ward_code,
    {{ clean_text('address_line') }} as address_line,
    cast(opened_on as date) as opened_on,
    cast(closed_on as date) as closed_on,
    {{ clean_code('status') }} as status,
    cast(created_at as timestamp) as created_at,
    cast(updated_at as timestamp) as updated_at,
    cast(_load_date as date) as _load_date
from {{ landed('store') }}
