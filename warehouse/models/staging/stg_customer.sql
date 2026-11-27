-- `customer` as it stands on the latest extract: the newest version of each key.
{{ latest_version('stg_customer__versions', ['customer_id']) }}
