-- Every landed version of `order_promotion`, typed and cleaned. One row per key per extract.
select
    cast(order_id as bigint) as order_id,
    cast(promotion_id as bigint) as promotion_id,
    cast(discount_amount as bigint) as discount_amount,
    cast(created_at as timestamp) as created_at,
    cast(updated_at as timestamp) as updated_at,
    cast(_load_date as date) as _load_date
from {{ landed('order_promotion') }}
