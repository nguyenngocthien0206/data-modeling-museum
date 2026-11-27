-- Every landed version of `product`, typed and cleaned. One row per key per extract.
select
    cast(product_id as bigint) as product_id,
    {{ clean_code('sku') }} as sku,
    {{ clean_text('product_name') }} as product_name,
    cast(category_id as bigint) as category_id,
    {{ clean_code('size') }} as size,
    cast(list_price as bigint) as list_price,
    cast(is_active as boolean) as is_active,
    cast(created_at as timestamp) as created_at,
    cast(updated_at as timestamp) as updated_at,
    cast(_load_date as date) as _load_date
from {{ landed('product') }}
