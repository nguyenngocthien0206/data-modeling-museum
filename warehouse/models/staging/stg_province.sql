-- `province` as it stands on the latest extract: the newest version of each key.
{{ latest_version('stg_province__versions', ['province_code']) }}
