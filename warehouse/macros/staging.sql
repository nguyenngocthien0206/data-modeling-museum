{#- Shared staging helpers. No business logic lives here (design section 5.2). -#}

{% macro landed(table_name) -%}
    {#- Every landed version of a source table, hiding extracts after as_of_load_date. -#}
    (
        select * from {{ source('landing', table_name) }}
        {%- if var('as_of_load_date') %}
        where _load_date <= cast('{{ var("as_of_load_date") }}' as date)
        {%- endif %}
    )
{%- endmacro %}

{% macro latest_version(versions_model, keys) -%}
    {#- The newest landed version of each key: the source as it stands on the last extract. -#}
    select *
    from {{ ref(versions_model) }}
    qualify row_number() over (
        partition by {{ keys | join(', ') }}
        order by _load_date desc, updated_at desc
    ) = 1
{%- endmacro %}

{% macro clean_text(column) -%}
    nullif(trim({{ column }}), '')
{%- endmacro %}

{% macro clean_code(column) -%}
    {#- Codes keep the source's own case convention; only blanks and padding go. -#}
    nullif(trim({{ column }}), '')
{%- endmacro %}

{% macro clean_phone(column) -%}
    {#- Digits only; an international 84 prefix becomes the national leading 0. -#}
    case
        when regexp_replace({{ column }}, '[^0-9]', '', 'g') like '84%'
            and length(regexp_replace({{ column }}, '[^0-9]', '', 'g')) = 11
        then '0' || substr(regexp_replace({{ column }}, '[^0-9]', '', 'g'), 3)
        else nullif(regexp_replace({{ column }}, '[^0-9]', '', 'g'), '')
    end
{%- endmacro %}

{% test unique_key(model, columns) %}
    {#- Fails for every key combination that appears more than once. -#}
    select {{ columns | join(', ') }}, count(*) as rows_per_key
    from {{ model }}
    group by {{ columns | join(', ') }}
    having count(*) > 1
{% endtest %}
