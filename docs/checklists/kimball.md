# Kimball review checklist

Source: Ralph Kimball and Margy Ross, *The Data Warehouse Toolkit: The Definitive Guide to Dimensional Modeling*, 3rd ed., Wiley, 2013. Chapter 2 ("Kimball Dimensional Modeling Techniques Overview") is the official catalogue of techniques; most rows cite it with the technique's name, plus the case-study chapter where the technique is worked through.

See [README.md](README.md) for how statuses work.

## Design

| ID | Item | Source | Status | Notes |
|---|---|---|---|---|
| K01 | Each business process (sales, shifts) goes through the four-step design: select the process, declare the grain, identify dimensions, identify facts | Ch. 2 (Four-Step Dimensional Design Process); Ch. 3 | | |
| K02 | The grain of every fact table is declared in business terms and written in its YAML | Ch. 2 (Declare the Grain); Ch. 3 | | |
| K03 | Fact tables are at the atomic grain the process captures | Ch. 2 (atomic grain); Ch. 3 | | |
| K04 | A bus matrix documents which conformed dimensions each process uses | Ch. 2 (Enterprise Data Warehouse Bus Matrix); Ch. 4 | | |

## Dimensions

| ID | Item | Source | Status | Notes |
|---|---|---|---|---|
| K05 | Store, product, date, customer, employee and promotion are conformed: one dimension shared by every fact that uses it | Ch. 2 (Conformed Dimensions); Ch. 4 | | |
| K06 | Every dimension has a surrogate key; the natural key is kept as an attribute | Ch. 2 (Dimension Surrogate Keys); Ch. 3 | | |
| K07 | A calendar date dimension exists and facts reference it | Ch. 2 (Calendar Date Dimensions); Ch. 3 | | |
| K08 | Facts never carry a null dimension key; unknown or not-applicable rows are used instead (for example guest orders) | Ch. 2 (null attributes and null foreign keys) | | |
| K09 | The order number is a degenerate dimension on the fact | Ch. 2 (Degenerate Dimensions); Ch. 3 | | |
| K10 | Dimensions are flattened (geography rolled into the dimension that uses it); any snowflaking is justified | Ch. 2 (Flattened Many-to-One Hierarchies; Snowflaked Dimensions) | | |
| K11 | Attributes are descriptive, decoded values, not bare codes | Ch. 3 (dimension attributes) | | |

## History

| ID | Item | Source | Status | Notes |
|---|---|---|---|---|
| K12 | The SCD technique is chosen per attribute and documented (type 1 or type 2, and why) | Ch. 2 (Slowly Changing Dimension Techniques); Ch. 5 | | |
| K13 | Type 2 rows carry effective date, expiration date and a current row indicator | Ch. 5 (Type 2: Add New Row) | | |
| K14 | Each fact row points to the dimension version in effect when the event happened | Ch. 5; Ch. 19 (surrogate key pipeline) | | |
| K15 | As-is reporting works next to as-was: current values reachable through type 1 columns on the type 2 row or a durable key (type 6 or type 7), choice documented | Ch. 5 (Type 6, Type 7) | | |

## Facts

| ID | Item | Source | Status | Notes |
|---|---|---|---|---|
| K16 | Facts are numeric and additive where possible; ratios are computed at query time, not stored | Ch. 2 (Additive, Semi-Additive, Non-Additive Facts) | | |
| K17 | Order-level facts (discount) are allocated to the line grain, so facts sum correctly at any level | Ch. 6 (Allocating Header Facts to the Line Item Level) | | |
| K18 | Different processes and grains live in separate fact tables (sales lines, shifts); no mixed grain | Ch. 2 (fact table grain) | | |

## Many-to-many

| ID | Item | Source | Status | Notes |
|---|---|---|---|---|
| K19 | Promotions per order are a multivalued dimension, modeled with a group key on the fact and a bridge table | Ch. 2 (Multivalued Dimensions and Bridge Tables); Ch. 14 (multivalued diagnoses) | | |
| K20 | The bridge carries a weighting factor that sums to 1 per group; weighted and impact use are documented | Ch. 14 (weighting factor) | | |

## Loading

| ID | Item | Source | Status | Notes |
|---|---|---|---|---|
| K21 | Late-arriving facts get the dimension version valid at event time, not the current one | Ch. 2 (Late Arriving Facts); Ch. 19 (late arriving data handler) | | |
| K22 | Corrections to facts follow one documented rule (replace the rows, or add adjustment rows) | Ch. 19 (fact table loading) | | |
| K23 | Every model, column, grain and SCD type is documented in YAML | Ch. 19 (metadata) | | |

## Allowed derived columns

- Decoded descriptions, hierarchy levels flattened into a dimension, calendar attributes in the date dimension (Ch. 2, Ch. 3).
- SCD housekeeping: effective date, expiration date, current indicator (Ch. 5).
- Allocated discount, gross and net amounts on the line fact (Ch. 6).
- Aggregated facts as dimension attributes (for example a customer's first purchase date), only if they serve the base requirements broadly, and each one listed in the PR (Ch. 2, Aggregated Facts as Dimension Attributes).

## Shared rules

| ID | Item | Source | Status | Notes |
|---|---|---|---|---|
| C01 | No structure exists only to serve a future challenge | Design 12.2 | | |
| C02 | Every table and column is justified by the base requirements or a row above | Design 12.2 | | |
| C03 | No aggregate built for a specific question | Design 6, 12.6 | | |
| C04 | Derived columns only from the allowed list | Design 12.2 | | |
| C05 | Incremental build equals a full refresh | Design 6 | | |
| C06 | Every table a question reads lives in `kimball.duckdb`; tuning limited to materialization and sort order | Design 6, 12.6 | | |
