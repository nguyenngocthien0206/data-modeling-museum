-- Every landed version of `employee`, typed and cleaned. One row per key per extract.
select
    cast(employee_id as bigint) as employee_id,
    {{ clean_text('full_name') }} as full_name,
    cast(home_store_id as bigint) as home_store_id,
    {{ clean_code('role') }} as role,
    cast(hired_on as date) as hired_on,
    cast(terminated_on as date) as terminated_on,
    cast(created_at as timestamp) as created_at,
    cast(updated_at as timestamp) as updated_at,
    cast(_load_date as date) as _load_date
from {{ landed('employee') }}
