{#
    dbt's default behavior concatenates "<target_schema>_<custom_schema_name>"
    (e.g. DEV_BRONZE). We want literal medallion schema names (BRONZE, SILVER,
    GOLD, PLATINUM) regardless of target, so override it to use the custom
    schema name as-is. See docs/decisions.md item F.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set default_schema = target.schema -%}
    {%- if custom_schema_name is none -%}
        {{ default_schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
