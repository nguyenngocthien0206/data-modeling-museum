-- `product_category` as it stands on the latest extract: the newest version of each key.
{{ latest_version('stg_product_category__versions', ['category_id']) }}
