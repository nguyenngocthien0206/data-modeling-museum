# One Big Table review checklist

One Big Table has no single canonical book. The rows below summarize what practitioner and vendor guidance recommends, plus the project rules from design section 6.4. Because the canon is thin, every row states where it comes from, and the "Project" rows are this repository's interpretation, open to challenge by PR.

Sources:

- Fivetran blog, star schema versus OBT benchmark, <https://fivetran.com/blog/star-schema-vs-obt> (benchmark on Redshift, Snowflake and BigQuery; flat tables mostly faster, about three times the storage).
- Google Cloud, BigQuery documentation, "Use nested and repeated fields", <https://docs.cloud.google.com/bigquery/docs/best-practices-performance-nested> (nested and repeated fields as the preferred way to denormalize one-to-many data).
- InterWorks, "Comparing Query Performance of Star Schemas vs. Flat Tables" (2024), <https://interworks.com/blog/2024/03/12/comparing-query-performance-of-star-schemas-vs-flat-tables/>.
- dbt Labs, "How we structure our dbt projects", <https://docs.getdbt.com/best-practices/how-we-structure/1-guide-overview> (staging, intermediate and marts layers).

See [README.md](README.md) for how statuses work.

## Layers

| ID | Item | Source | Status | Notes |
|---|---|---|---|---|
| O01 | Wide tables are built from a tested intermediate layer, never straight from raw sources | dbt Labs (intermediate layer); Project (design 6.4) | | |
| O02 | The intermediate layer holds reusable building blocks (histories, corrected orders), not question-specific results | dbt Labs; Project | | |

## Wide tables

| ID | Item | Source | Status | Notes |
|---|---|---|---|---|
| O03 | One wide table per business process (`obt_sales`, `obt_shifts`); each extra table is recorded and counted | Project (ADR-0004) | | |
| O04 | The grain of each wide table is declared and tested | Project | | |
| O05 | Descriptive attributes are denormalized into the row, so the main questions need no joins | Fivetran; InterWorks | | |
| O06 | One-to-many and many-to-many context (promotions per order) is kept as nested repeated fields (`LIST<STRUCT>`), not by fanning out rows | BigQuery docs | | |
| O07 | Changing attributes appear as explicit as-was and as-is columns with distinct names (for example `customer_tier_at_order`, `customer_tier_current`) | Project | | |
| O08 | Order-level measures cannot be double counted when summed over line rows (allocation, or a first-line flag), and the rule is documented | Project | | |
| O09 | Every column is documented with its meaning and its time semantics (as-was or as-is) | Project | | |

## Operations

| ID | Item | Source | Status | Notes |
|---|---|---|---|---|
| O10 | The incremental strategy is documented: which upstream change rewrites which rows (for example a current-tier change rewrites every row of that customer) | Project | | |
| O11 | Storage growth from duplication is measured, not assumed | Fivetran (storage) | | |

## Allowed derived columns

- As-was and as-is pairs for every changing attribute (O07).
- Date parts of the order timestamp (date, week, month, quarter, hour).
- Allocated order-level measures or a first-line flag (O08).
- Customer-level lifetime attributes commonly precomputed in wide tables (for example first order date), only if they serve the base requirements broadly, and each one listed in the PR.

## Shared rules

| ID | Item | Source | Status | Notes |
|---|---|---|---|---|
| C01 | No structure exists only to serve a future challenge | Design 12.2 | | |
| C02 | Every table and column is justified by the base requirements or a row above | Design 12.2 | | |
| C03 | No aggregate built for a specific question | Design 6, 12.6 | | |
| C04 | Derived columns only from the allowed list | Design 12.2 | | |
| C05 | Incremental build equals a full refresh | Design 6 | | |
| C06 | Every table a question reads lives in `obt.duckdb`; tuning limited to materialization and sort order | Design 6, 12.6 | | |
