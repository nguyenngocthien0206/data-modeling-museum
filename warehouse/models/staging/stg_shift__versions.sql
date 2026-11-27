-- Every landed version of `shift`, typed and cleaned. One row per key per extract.
select
    cast(shift_id as bigint) as shift_id,
    cast(store_id as bigint) as store_id,
    cast(employee_id as bigint) as employee_id,
    cast(shift_start as timestamp) as shift_start,
    cast(shift_end as timestamp) as shift_end,
    cast(created_at as timestamp) as created_at,
    cast(updated_at as timestamp) as updated_at,
    cast(_load_date as date) as _load_date
from {{ landed('shift') }}
