# Pre-registered predictions

Written on 2026-11-27, before any data, model or metric code exists. Locked in `fairness-lock.json` (design section 11.2) by the PR that adds it. This file is never edited after that PR is merged; `docs/findings.md` compares every line below with the measured result and explains each miss.

How to read it:

- Rankings go from best (1) to worst (4) for that metric. `=` means "too close to call".
- Confidence: **high** (we would be surprised to be wrong), **medium**, **low** (closer to a guess).
- Each prediction names the home-turf claim it tests (design section 12.3), where there is one.
- "Core" and "presentation" are the two layers of each model (design section 6). For Kimball they are the same.

## Consumption

### SQL complexity, presentation layer (Q01 to Q10)

| Rank | Model | Confidence |
|---|---|---|
| 1 | obt | medium |
| 2 | kimball = 3nf mart = data_vault mart | medium |

Tests the OBT claim "fewest joins". The three marts are all star schemas, so their SQL should be nearly identical. OBT should need the fewest joins, but it may not win on CTE count: Q03 needs to unnest promotions and Q10 still needs a self-join, and order-level measures on a line-grain table can force an extra step.

### SQL complexity, core layer (Q01 to Q10)

| Rank | Model | Confidence |
|---|---|---|
| 1 | kimball | high |
| 2 | obt (intermediate) | medium |
| 3 | 3nf (EDW) | high |
| 4 | data_vault (raw and business vault) | high |

Kimball's core is its star. The 3NF EDW needs a join per normalized entity and per history table. Data Vault needs hub, link and satellite hops for every attribute; PIT and bridge tables soften this but do not remove it. Expect Data Vault core SQL to have at least twice the joins of Kimball on the as-was questions (Q02, Q05, Q06).

### Query time, presentation layer (large scale)

| Rank | Model | Confidence |
|---|---|---|
| 1 | obt | medium |
| 2 | kimball = 3nf mart = data_vault mart | medium |

Tests the OBT claim "fast scans on columnar engines". DuckDB joins small dimensions to a 30 million row fact quickly, so we expect OBT to be faster on most questions but by less than a factor of two, not by an order of magnitude.

### Query time, core layer (large scale)

| Rank | Model | Confidence |
|---|---|---|
| 1 | kimball | medium |
| 2 | obt (intermediate) | low |
| 3 | 3nf (EDW) | medium |
| 4 | data_vault | medium |

## Production

### Full build time (large scale)

| Rank | Model | Confidence |
|---|---|---|
| 1 | kimball | low |
| 2 | obt | low |
| 3 | 3nf | low |
| 4 | data_vault | low |

Kimball builds one layer. OBT builds an intermediate layer plus a very wide table. 3NF builds two full layers. Data Vault builds many tables, computes MD5 hash keys on every row, then PIT, bridge and a mart on top.

### Daily incremental time (large scale)

| Rank | Model | Confidence |
|---|---|---|
| 1 | data_vault | medium |
| 2 | kimball | medium |
| 3 | 3nf | low |
| 4 | obt | medium |

Tests the Data Vault claim "insert-only, parallel loading". OBT should be the most expensive on days with many attribute changes (the monthly tier recompute on the 1st): every as-is column change rewrites all line rows of that customer.

### Storage (large scale, whole model)

| Rank | Model | Confidence |
|---|---|---|
| 1 | kimball | medium |
| 2 | obt | low |
| 3 | 3nf | medium |
| 4 | data_vault | medium |

Columnar compression should absorb much of OBT's duplication, so we expect OBT at less than twice Kimball, not the three times seen in some row-store benchmarks. 3NF and Data Vault each store a core plus a mart; Data Vault also stores 32-character hash keys on every row.

### Code size

| Metric | Prediction | Confidence |
|---|---|---|
| Number of dbt models, fewest to most | obt, kimball, 3nf, data_vault | high |
| Hand-written lines, fewest to most (framework excluded) | obt, kimball, data_vault, 3nf | low |
| Framework lines | only data_vault has any | high |
| Generated (compiled) lines, most | data_vault, by a wide margin | high |

Data Vault model files are mostly short macro calls, so its hand-written lines may be modest while its compiled SQL is the largest. 3NF has the most hand-written SQL because it builds two layers by hand.

## Evolution

For each challenge: who changes the least, who changes the most, and who pays the most backfill. "Additive share" is added lines over all changed lines.

### N1.1 Administrative boundary merger

| Metric | Best | Worst | Confidence |
|---|---|---|---|
| Lines changed | kimball | obt | medium |
| Additive share | data_vault | obt | medium |
| Backfill cost (time and rows reprocessed) | data_vault | obt | medium |
| Old questions still correct without SQL changes | kimball, 3nf, data_vault | obt | low |

Tests the Kimball claim "as-was and as-is through SCD2". OBT has to add new-boundary columns to every sales row, which means rewriting the whole wide table.

### N2.1 Delivery partner source with overlapping customers

| Metric | Best | Worst | Confidence |
|---|---|---|---|
| Additive share | data_vault | kimball | high |
| Models touched | data_vault | obt | medium |
| Backfill cost | data_vault | obt | medium |

Tests the Data Vault claim "new sources are additive". Kimball has to change its conformed customer dimension to resolve identities; OBT rebuilds its sales table with new channel and identity columns.

### N2.2 Inventory and ingredients

| Metric | Best | Worst | Confidence |
|---|---|---|---|
| Additive share | 3nf = data_vault = kimball | obt | medium |
| SQL complexity of the cost-per-cup question | kimball | data_vault | medium |
| New wide tables needed | n/a | obt needs at least one | high |

Tests the 3NF claim "new subject areas fit the integrated model" and the Kimball claim "drill-across through conformed dimensions".

### N2.3 App event log

| Metric | Best | Worst | Confidence |
|---|---|---|---|
| SQL complexity of funnel questions | obt | data_vault | high |
| Daily incremental time for events | obt = kimball | data_vault | medium |
| Storage for events | kimball | data_vault | low |

Tests the OBT claim "high-volume events in a wide table". Hashing every event key in Data Vault should cost real time at ten times the line volume.

## Governance

### G1 Personal data erasure

| Metric | Best | Worst | Confidence |
|---|---|---|---|
| Tables touched | data_vault | obt | medium |
| Rows updated or deleted | 3nf | obt, by orders of magnitude | high |
| Time spent | 3nf = data_vault | obt | medium |
| Personal data left behind after a first honest attempt | none expected | kimball (history rows) | low |

Tests the Data Vault claim "PII isolated in its own satellite". Data Vault still has to refresh the PIT and the information mart, which carry names, so its advantage may be smaller than claimed. OBT copies personal data into every sales row.

## Hidden questions

| Metric | Prediction | Confidence |
|---|---|---|
| Answerable without model changes (out of 5) | 3nf core 5, data_vault core 5, kimball 4, obt 3 | medium |
| SQL complexity where answerable, lowest | obt | medium |
| SQL complexity where answerable, highest | data_vault core | high |

Tests the 3NF claim "flexible for unforeseen questions". We expect OBT to fail on the new many-to-many path (H3) and the cross-process question (H4), and Kimball to struggle with the ad-hoc grain (H5).

## What would surprise us

- OBT is not the fastest on presentation-layer queries at the large scale.
- Data Vault is not the cheapest daily incremental load.
- Kimball needs a model change for more than one hidden question.
- OBT storage is within 1.3 times Kimball's.
- The 3NF mart's question SQL is noticeably different from Kimball's.
- Data Vault erasure touches more tables than Kimball's.
