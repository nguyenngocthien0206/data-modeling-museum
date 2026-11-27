-- `sales_order` as it stands on the latest extract: the newest version of each key.
{{ latest_version('stg_sales_order__versions', ['order_id']) }}
