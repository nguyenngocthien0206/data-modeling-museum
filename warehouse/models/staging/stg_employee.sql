-- `employee` as it stands on the latest extract: the newest version of each key.
{{ latest_version('stg_employee__versions', ['employee_id']) }}
