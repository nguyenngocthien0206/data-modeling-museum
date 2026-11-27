-- Every landed version of `order_line`, typed and cleaned. One row per key per extract.
select
    cast(order_id as bigint) as order_id,
    cast(line_no as integer) as line_no,
    cast(product_id as bigint) as product_id,
    cast(quantity as integer) as quantity,
    cast(unit_price as bigint) as unit_price,
    cast(line_amount as bigint) as line_amount,
    cast(created_at as timestamp) as created_at,
    cast(updated_at as timestamp) as updated_at,
    cast(_load_date as date) as _load_date
from {{ landed('order_line') }}
