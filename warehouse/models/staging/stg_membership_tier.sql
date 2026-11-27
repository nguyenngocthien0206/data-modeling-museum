-- `membership_tier` as it stands on the latest extract: the newest version of each key.
{{ latest_version('stg_membership_tier__versions', ['tier_code']) }}
