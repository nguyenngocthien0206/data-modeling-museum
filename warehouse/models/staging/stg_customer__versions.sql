-- Every landed version of `customer`, typed and cleaned. One row per key per extract.
select
    cast(customer_id as bigint) as customer_id,
    {{ clean_text('full_name') }} as full_name,
    {{ clean_phone('phone') }} as phone,
    lower({{ clean_text('email') }}) as email,
    cast(date_of_birth as date) as date_of_birth,
    {{ clean_code('gender') }} as gender,
    {{ clean_text('address_line') }} as address_line,
    {{ clean_code('ward_code') }} as ward_code,
    {{ clean_code('tier_code') }} as tier_code,
    cast(joined_at as timestamp) as joined_at,
    cast(created_at as timestamp) as created_at,
    cast(updated_at as timestamp) as updated_at,
    cast(_load_date as date) as _load_date
from {{ landed('customer') }}
