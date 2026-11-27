-- `order_promotion` as it stands on the latest extract: the newest version of each key.
{{ latest_version('stg_order_promotion__versions', ['order_id', 'promotion_id']) }}
