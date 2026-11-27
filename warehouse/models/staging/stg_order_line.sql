-- `order_line` as it stands on the latest extract: the newest version of each key.
{{ latest_version('stg_order_line__versions', ['order_id', 'line_no']) }}
