# Data Vault 2.0 review checklist

Source: Dan Linstedt and Michael Olschimke, *Building a Scalable Data Warehouse with Data Vault 2.0*, Morgan Kaufmann, 2016 (abbreviated "DV2"). Rows cite chapters where checked; otherwise the topic.

See [README.md](README.md) for how statuses work.

## Architecture

| ID | Item | Source | Status | Notes |
|---|---|---|---|---|
| DV01 | The raw vault stores source data as delivered; only hard rules (typing, normalization of keys) are applied before it | DV2 Ch. 2 (hard and soft business rules) | | |
| DV02 | Soft business rules live in the business vault or the information marts, never in the raw vault | DV2 Ch. 2 | | |
| DV03 | The business vault is sparse: only computed structures that downstream layers need | DV2 Ch. 2; Ch. 5 (computed satellites); Ch. 6 | | |
| DV04 | Information marts are built from the raw and business vault only | DV2 Ch. 2; Ch. 14 (loading the dimensional information mart) | | |

## Hubs

| ID | Item | Source | Status | Notes |
|---|---|---|---|---|
| DV05 | One hub per core business concept, holding only hash key, business key, load date and record source | DV2 Ch. 4 (hubs) | | |
| DV06 | Business keys are the keys the business uses; where a source id is used instead, the choice is documented | DV2 Ch. 4 (business keys) | | |
| DV07 | Hash keys follow one documented recipe: trim, upper case, fixed delimiter, null replacement, MD5 | DV2 Ch. 11 (hashing in the data warehouse) | | |

## Links

| ID | Item | Source | Status | Notes |
|---|---|---|---|---|
| DV08 | Links model relationships and units of work between hubs and carry no descriptive attributes | DV2 Ch. 4 (links) | | |
| DV09 | Links are many-to-many by design, even when the source relationship is one-to-many today | DV2 Ch. 4 | | |
| DV10 | A dependent child key is used where the relationship needs a sequence (order line number) | DV2 Ch. 4 (dependent child) | | |

## Satellites

| ID | Item | Source | Status | Notes |
|---|---|---|---|---|
| DV11 | Satellites hold descriptive context with load date, record source and hash diff, and have exactly one parent | DV2 Ch. 4 (satellites) | | |
| DV12 | Satellites are split by rate of change and by source system | DV2 Ch. 4 (splitting satellites) | | |
| DV13 | Personal data sits in its own satellite, separate from non-sensitive context | Common DV 2.0 practice (split by data classification); chapter not checked | | |
| DV14 | Effectivity satellites track begin and end of driving-key relationships (customer to ward, store to ward) | DV2 Ch. 5 (effectivity satellites) | | |
| DV15 | Voided or deleted source records are tracked (status tracking or a status attribute), never removed | DV2 Ch. 5 (status tracking satellites) | | |

## Loading

| ID | Item | Source | Status | Notes |
|---|---|---|---|---|
| DV16 | Loads are insert-only; nothing in the raw vault is updated in place (end dates, if any, are derived) | DV2 Ch. 12 (loading the Data Vault) | | |
| DV17 | Load date is when the data arrived in the warehouse (`_load_date`), never a business date | DV2 Ch. 4; Ch. 11 | | |
| DV18 | Several versions of one key in a single batch are all loaded, in order | DV2 Ch. 12 | | |
| DV19 | Hubs, links and satellites load without dependencies on each other, thanks to hash keys | DV2 Ch. 2; Ch. 12 | | |
| DV20 | Raw vault structures are generated from the macro library, not hand-written one by one | DV2 Ch. 3 (automation in the methodology) | | |

## Query assistance

| ID | Item | Source | Status | Notes |
|---|---|---|---|---|
| DV21 | PIT tables per hub give satellite lookups per snapshot date | DV2 Ch. 6 (point-in-time tables) | | |
| DV22 | Ghost records (zero keys) let PIT lookups use inner joins | DV2 Ch. 6 | | |
| DV23 | Bridge tables shortcut frequently used link paths | DV2 Ch. 6 (bridge tables) | | |
| DV24 | Static code lists (channel, tier) are reference tables, not hubs | DV2 Ch. 6 (reference tables) | | |

## Allowed derived columns

- Hash keys and hash diffs (DV2 Ch. 4, Ch. 11).
- Anything in the business vault: computed satellites, PIT, bridge (DV2 Ch. 5, Ch. 6).
- In the information mart, the same derived columns the Kimball checklist allows, since the mart is dimensional (DV2 Ch. 14).
- Nothing derived in the raw vault.

## Shared rules

| ID | Item | Source | Status | Notes |
|---|---|---|---|---|
| C01 | No structure exists only to serve a future challenge | Design 12.2 | | |
| C02 | Every table and column is justified by the base requirements or a row above | Design 12.2 | | |
| C03 | No aggregate built for a specific question | Design 6, 12.6 | | |
| C04 | Derived columns only from the allowed list | Design 12.2 | | |
| C05 | Incremental build equals a full refresh | Design 6 | | |
| C06 | Every table a question reads lives in `data_vault.duckdb`; tuning limited to materialization and sort order | Design 6, 12.6 | | |
