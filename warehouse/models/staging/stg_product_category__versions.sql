-- Every landed version of `product_category`, typed and cleaned. One row per key per extract.
select
    cast(category_id as bigint) as category_id,
    {{ clean_text('category_name') }} as category_name,
    cast(created_at as timestamp) as created_at,
    cast(updated_at as timestamp) as updated_at,
    cast(_load_date as date) as _load_date
from {{ landed('product_category') }}
