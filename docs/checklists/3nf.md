# 3NF (Inmon CIF) review checklist

Sources:

- W. H. Inmon, *Building the Data Warehouse*, 4th ed., Wiley, 2005 (abbreviated "BtDW").
- W. H. Inmon, Claudia Imhoff and Ryan Sousa, *Corporate Information Factory*, 2nd ed., Wiley, 2001 (abbreviated "CIF").

Rows cite chapters where checked; otherwise the topic.

See [README.md](README.md) for how statuses work.

## The four defining properties

| ID | Item | Source | Status | Notes |
|---|---|---|---|---|
| N01 | Subject-oriented: the EDW is organized around major subjects (customer, product, store, sales, workforce), not around source systems | BtDW Ch. 2 (definition of the data warehouse) | | |
| N02 | Integrated: one key, one encoding and one unit per concept, whatever the source | BtDW Ch. 2 | | |
| N03 | Time-variant: every record carries a time element and history is kept | BtDW Ch. 2 | | |
| N04 | Nonvolatile: loaded data is not updated in place; corrections arrive as new versions | BtDW Ch. 2 | | |

## Core design

| ID | Item | Source | Status | Notes |
|---|---|---|---|---|
| N05 | The EDW follows a corporate data model normalized to 3NF: no repeating groups, no partial or transitive dependencies | BtDW Ch. 3 (the data model: ERD, data item sets, physical model) | | |
| N06 | The EDW keeps data at the lowest useful grain | BtDW Ch. 4 (granularity) | | |
| N07 | Warehouse keys are independent of source keys; source keys are kept for lineage | BtDW (integration, topic) | | |
| N08 | Changing attributes are stored as effective-dated records (from and to dates), not overwritten | BtDW (continuous versus discrete records, topic) | | |
| N09 | Reference data (tiers, channels, geography) is managed in the EDW with its history | BtDW (reference data, topic) | | |
| N10 | Transactions keep every landed version with its load date and a current-version flag | BtDW Ch. 2 (nonvolatile); project design 6.1 | | |

## Factory architecture

| ID | Item | Source | Status | Notes |
|---|---|---|---|---|
| N11 | Integration and transformation happen before the EDW (here: staging plus core transforms), not inside the marts | CIF (integration and transformation layer) | | |
| N12 | Data marts are fed only from the EDW, never from staging or sources | CIF (data marts fed by the data warehouse) | | |
| N13 | Marts are shaped for their users; the dimensional form is the usual CIF choice | CIF (data mart types) | | |
| N14 | Derived and summarized data belong in the marts, not in the EDW | CIF (data warehouse versus data marts) | | |

## Allowed derived columns

- In the EDW: warehouse keys, effective dates, current-version flags, load dates. Nothing else derived (N14).
- In the mart: the same derived columns the Kimball checklist allows, since the mart is dimensional.

## Shared rules

| ID | Item | Source | Status | Notes |
|---|---|---|---|---|
| C01 | No structure exists only to serve a future challenge | Design 12.2 | | |
| C02 | Every table and column is justified by the base requirements or a row above | Design 12.2 | | |
| C03 | No aggregate built for a specific question | Design 6, 12.6 | | |
| C04 | Derived columns only from the allowed list | Design 12.2 | | |
| C05 | Incremental build equals a full refresh | Design 6 | | |
| C06 | Every table a question reads lives in `3nf.duckdb`; tuning limited to materialization and sort order | Design 6, 12.6 | | |
