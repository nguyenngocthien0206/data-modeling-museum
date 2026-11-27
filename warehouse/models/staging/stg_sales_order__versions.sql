-- Every landed version of `sales_order`, typed and cleaned. One row per key per extract.
select
    cast(order_id as bigint) as order_id,
    cast(store_id as bigint) as store_id,
    cast(customer_id as bigint) as customer_id,
    cast(cashier_employee_id as bigint) as cashier_employee_id,
    {{ clean_code('channel_code') }} as channel_code,
    cast(ordered_at as timestamp) as ordered_at,
    {{ clean_code('status') }} as status,
    cast(created_at as timestamp) as created_at,
    cast(updated_at as timestamp) as updated_at,
    cast(_load_date as date) as _load_date
from {{ landed('sales_order') }}
