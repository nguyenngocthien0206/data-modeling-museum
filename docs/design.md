# Design: data-modeling-museum

One coffee chain, four data models. This document describes how the repository is built, how the four models are compared, and the rules that keep the comparison fair. It is the reference for every issue and PR.

Status: draft for review (step 1).

## 1. Purpose

The debate "Kimball or Data Vault or One Big Table" usually runs on personal experience. This repository builds all four contenders on the same data, makes them answer the same questions, puts them through the same business changes, and measures the results.

The goal is not to crown a winner. The goal is to show which model fits which situation, with numbers behind each claim. Choosing a model is a trade between upfront build effort, daily operating cost, how easily new people can query it, and how much a team has to coordinate when the business changes. Every metric below exists to make one side of that trade visible.

The four models:

| Model | Core layer | Presentation layer | Canon |
|---|---|---|---|
| `3nf` | Normalized, integrated, time-variant enterprise warehouse | Dimensional data mart built from the core | Inmon, Corporate Information Factory |
| `kimball` | Star schema with conformed dimensions (core and presentation are the same) | Same | Kimball Group, The Data Warehouse Toolkit, 3rd ed. |
| `data_vault` | Raw vault (hubs, links, satellites) plus a thin business vault (PIT, bridge) | Information mart | Linstedt and Olschimke, Building a Scalable Data Warehouse with Data Vault 2.0 |
| `obt` | Intermediate layer that prepares clean, history-aware building blocks | One wide table per business process | Common practice on columnar engines |

All four read from one shared staging layer, so any difference after staging comes from modeling alone. Each model is measured at both its core and its presentation layer.

## 2. Five evaluation axes

| Axis | Question it answers | Main metrics |
|---|---|---|
| Correctness | Does it give the right answer? | Match against independent reference answers |
| Consumption | Is it easy and fast to query? | SQL complexity, query time |
| Production | What does it cost to build and run every day? | Full build time, daily incremental time, storage, code size |
| Evolution | What does a business change or extension cost? | Files and models touched, lines changed, share of additive change, regressions, backfill cost |
| Governance | Can it erase personal data, reproduce old reports, trace lineage? | Tables and rows touched, intervention time, automated verification |

There is no total score. The axes are never summed. Findings are written per situation (section 12.7).

## 3. Source system

A simulated OLTP point-of-sale and membership system for a coffee chain in Vietnam. It is the single input for all four models.

### 3.1 Tables

| Table | Key | Main columns | Mutability |
|---|---|---|---|
| `province` | `province_code` | `province_name` | Rare changes |
| `district` | `district_code` | `province_code`, `district_name` | Rare changes |
| `ward` | `ward_code` | `district_code`, `ward_name` | Rare changes |
| `store` | `store_id` | `store_code`, `store_name`, `ward_code`, `address_line`, `opened_on`, `closed_on`, `status` | Overwritten |
| `channel` | `channel_code` | `channel_name` (`dine_in`, `takeaway`) | Static |
| `membership_tier` | `tier_code` | `tier_name`, `rank`, `min_spend_12m` | Static |
| `customer` | `customer_id` | `full_name`, `phone`, `email`, `date_of_birth`, `gender`, `address_line`, `ward_code`, `tier_code`, `joined_at` | Overwritten |
| `product_category` | `category_id` | `category_name` | Static |
| `product` | `product_id` | `sku`, `product_name`, `category_id`, `size`, `list_price`, `is_active` | Overwritten |
| `promotion` | `promotion_id` | `promo_code`, `promo_name`, `promo_type`, `promo_value`, `starts_on`, `ends_on` | Overwritten |
| `employee` | `employee_id` | `full_name`, `home_store_id`, `role`, `hired_on`, `terminated_on` | Overwritten |
| `shift` | `shift_id` | `store_id`, `employee_id`, `shift_start`, `shift_end` | Inserted, sometimes corrected |
| `sales_order` | `order_id` | `store_id`, `customer_id` (null for guests), `cashier_employee_id`, `channel_code`, `ordered_at`, `status` (`completed`, `voided`) | Inserted, sometimes corrected |
| `order_line` | `order_id`, `line_no` | `product_id`, `quantity`, `unit_price`, `line_amount` | Inserted, sometimes corrected |
| `order_promotion` | `order_id`, `promotion_id` | `discount_amount` | Inserted, sometimes corrected |

Every table carries `created_at` and `updated_at`.

Like most real POS systems, the source keeps only the current state. When a customer changes tier or address, or a product changes price, the old value is overwritten. History exists only if the warehouse keeps it. That is exactly where the four models differ.

### 3.2 Business definitions

- Money is integer VND (`BIGINT`), as in a real Vietnamese POS. No minor units. The multi-currency challenge pays the cost of changing this, on purpose.
- `line_amount = quantity * unit_price`. `unit_price` is what was actually charged. It usually equals the list price in effect at order time, with a small share of manual overrides.
- Gross revenue of an order is the sum of its `line_amount`. Discount is the sum of its `order_promotion.discount_amount`. Net revenue is gross minus discount.
- Only `completed` orders count as revenue. A `voided` order counts for nothing.
- An order can carry zero, one or several promotions.
- All timestamps are local time (Asia/Ho_Chi_Minh) without time zone, as the source stores them. Weeks are ISO weeks starting Monday.
- Every main question is defined at a grain where the answer does not depend on how a model allocates order-level discounts to lines. Allocation is a modeling choice, and rounding must not decide correctness.

## 4. Data generation

### 4.1 Timeline

- Base period: 2024-01-01 to 2025-06-30 (546 days). It ends the day before Vietnam's 2025 administrative reorganization takes effect (2025-07-01), so the merger challenge can happen "live" after the base.
- Challenges append extra days after the base period. Each challenge is applied on its own to the frozen base, never on top of another challenge.

### 4.2 Daily extracts

The generator simulates the source day by day. At the end of each day it writes a delta extract of every table: all rows whose `updated_at` falls in that day, in their end-of-day state. This is the most common batch extraction pattern in practice.

```
data/<scale>/landing/<table>/load_date=YYYY-MM-DD/part-0.parquet
```

Each row carries `_load_date`. A key appears at most once per extract. Intra-day intermediate states are lost, exactly as they would be with a real watermark extract, and this loss is the same for every model and for the reference answers.

### 4.3 What changes over time

| Change | Rule |
|---|---|
| New members | Steady sign-ups, more in promotion periods |
| Tier changes | On the 1st of each month, tier is recomputed from trailing 12-month net spend. Upgrades and downgrades both happen |
| Address moves | A small monthly share of members move, sometimes to another province |
| List price changes | A few chain-wide price rounds plus individual product changes, at any time of day |
| Store lifecycle | New stores open throughout the period, a few close |
| Workforce | Hires and terminations, home store transfers |
| Promotions | Campaigns with date ranges; some orders stack two or three promotions |

### 4.4 Late and corrected data

- Late-arriving: a share of orders come from stores with offline POS and land 1 to 3 days after `ordered_at`.
- Corrected: a share of orders are later fixed (line quantity changed, line removed, promotion discount adjusted) or voided. The fix arrives in a later extract with a new `updated_at`.
- Shifts are occasionally corrected (end time fixed).

Without late and corrected data, the comparison of history handling would be meaningless.

### 4.5 Realism and determinism

- Faker with locale `vi_VN` generates people and addresses (names, phone numbers, emails, street lines). It is used only for entities, because it is too slow for tens of millions of order lines.
- Orders, lines and promotions are generated with numpy in daily batches and written with pyarrow.
- Every random stream is seeded from `(global_seed, table, day)`. The same seed always gives byte-identical parquet, and days can be generated in parallel.
- Province names are real (Ha Noi, TP. Ho Chi Minh, Binh Duong, Ba Ria - Vung Tau, Dong Nai, Hai Phong, Hai Duong, Da Nang, Quang Nam, Can Tho, Khanh Hoa and a few more). Districts and wards are simulated. The merger challenge follows the real 2025 provincial merges for these provinces, simplified to merges only (no ward splits).

### 4.6 Scale profiles

| Profile | Stores (end of base) | Order lines (approx.) | Use |
|---|---|---|---|
| `small` | 8 | 150 thousand | CI, tests, development |
| `medium` | 40 | 3 million | Local checks before a large run |
| `large` | 150 | 30 million | Benchmark |

Profiles are YAML files. All profiles cover the full 546-day timeline so that every question (cohorts, year-over-year growth) is meaningful at every scale.

### 4.7 Truth manifest

The generator also writes `truth_manifest.json` with facts it knows from the simulation: final completed order count, final net revenue per day, number of tier changes, number of late and corrected orders. These are used to test the reference answers themselves (section 8).

## 5. Landing and staging

### 5.1 Landing is an immutable archive

The landing zone keeps every daily extract forever and is never modified, like the bronze layer of a modern lakehouse. Consequences:

- Any model can be rebuilt from scratch at any time. When a challenge needs a rebuild, that is allowed, and its real cost (time and data reprocessed) is measured.
- This assumption weakens one claimed advantage of Data Vault and Inmon: being the only durable store of history. It is listed as a limitation (section 15) and recorded in ADR-0002.
- Erasing personal data must also purge the landing archive. That step is the same for all models and is reported separately.

### 5.2 Shared staging

A set of dbt views over the landing parquet, used by all four models:

- Type casting, trimming, consistent snake_case naming, code normalization (for example phone numbers to one format).
- Two shapes per table: `stg_<table>__versions` (every landed version with `_load_date` and `updated_at`) and `stg_<table>` (latest version per key).
- A dbt var `as_of_load_date` hides all extracts after a given date. This is how the pipeline simulates "today is day D" for incremental runs.

Staging contains no business logic and no modeling decisions. If a rule could reasonably be done differently by different models, it does not belong in staging.

## 6. The four models

General rules for all models:

- The presentation layer is kept at atomic grain. No aggregate table built for a specific question.
- No structure that only serves a challenge that has not happened yet (section 12.2).
- Every table a question reads is materialized inside the model's own DuckDB file.
- Incremental loads are supported for every structure that grows daily.

### 6.1 `3nf`: Inmon Corporate Information Factory

Core: the enterprise data warehouse (EDW), subject-oriented, integrated, time-variant and non-volatile.

- Normalized entities with their own warehouse keys and the source business keys: `geo_province`, `geo_district`, `geo_ward`, `store`, `customer`, `product_category`, `product`, `promotion`, `employee`, `channel`, `membership_tier`.
- Time variance through effective-dated history tables for attributes that change: `customer_tier_history`, `customer_address_history`, `product_price_history`, `store_status_history`, `employee_assignment_history`.
- Transactions (`sales_order`, `order_line`, `order_promotion`, `shift`) are non-volatile: each landed version is kept with its load date, and the current version is flagged. Corrections are visible, never overwritten.

Presentation: a dimensional data mart derived from the EDW, as the CIF prescribes. It will look similar to the Kimball star. That is a finding, not a flaw: in a CIF the difference lives in the core, in build cost, and in how change propagates.

### 6.2 `kimball`: dimensional bus

Core and presentation are the same star schema.

- Dimensions: `dim_date`, `dim_store` (SCD2), `dim_product` (SCD2 on list price and descriptive attributes), `dim_customer` (SCD2 on tier and address), `dim_geography` (SCD2), `dim_channel`, `dim_employee` (SCD2 on home store), `dim_promotion`.
- SCD2 is built from staging versions with window functions (`valid_from`, `valid_to`, `is_current`), as incremental models. dbt snapshots are not used, see ADR-0001.
- Facts: `fct_sales_line` at order line grain, with order-level discount allocated to lines (proportional, largest remainder rounding so totals stay exact), and `fct_shift` at shift grain.
- Order to promotion is many-to-many: a promotion group key on the fact and `bridge_promotion_group` with a weighting factor, following the multivalued dimension pattern in the Toolkit.
- Guest orders point to an unknown member row in `dim_customer`.
- Late-arriving facts are matched to the dimension version in effect at `ordered_at`. Corrections replace the affected fact rows through incremental delete and insert.

### 6.3 `data_vault`: Data Vault 2.0

Core: raw vault plus a thin business vault.

- Hubs: customer, store, product, employee, promotion, order, ward.
- Links: order-customer, order-store, order-employee, order-line (order to product with `line_no` as dependent child key), order-promotion, customer-ward, store-ward, shift (employee, store).
- Satellites split by rate of change and sensitivity: `sat_customer_pii` (name, phone, email, birth date, address line) separate from `sat_customer_membership` (tier). Product descriptive attributes separate from `sat_product_price`.
- Effectivity satellites for driving-key relationships (customer to ward, store to ward).
- Hash keys are MD5 over trimmed, upper-cased, delimited business keys. `load_date` comes from `_load_date`, `record_source` from the source table. Hash diffs detect changes, so a multi-version initial load and a daily load use the same code.
- Business vault: PIT tables for customer, product and store; a bridge over order lines.

Presentation: an information mart (star) built from PIT and bridge.

The packages automate_dv and datavault4dbt do not support DuckDB, so the model uses a small in-repo macro library (hash key, hub, link, satellite, effectivity satellite, PIT). Its lines are counted as framework code, separately from the model itself. See ADR-0003.

### 6.4 `obt`: One Big Table

Nobody builds a big table straight from raw sources, so there are two layers.

- Intermediate: deduplicated current rows, version histories for customer, product and store, orders with corrections applied, promotions per order.
- Presentation: one wide table per business process. `obt_sales` at order line grain, with as-was and as-is attributes side by side (for example `customer_tier_at_order` and `customer_tier_current`), list price in effect, and promotions stored as `LIST<STRUCT>` so the many-to-many relation does not fan out rows. `obt_shifts` at shift grain. Any additional table is recorded and counted. See ADR-0004.

## 7. Business questions

Ten main questions. All four models must answer all ten, at both layers.

| ID | Question | What it stresses |
|---|---|---|
| Q01 | Net revenue per store per ISO week | Baseline |
| Q02 | Net revenue per membership tier, by tier at order time and by current tier, with a guest bucket | SCD2 as-was vs as-is |
| Q03 | Per promotion: orders applied, total discount, gross and net revenue of those orders; plus a check row with distinct orders and total discount across all promotions | Many-to-many without double counting |
| Q04 | Monthly cohort retention: members grouped by month of first completed order, share buying again in months +1 to +6 | Per-customer time logic |
| Q05 | Net revenue per province of the member's home address, at order time and current | Geographic history |
| Q06 | For each list price change: units sold in the 14 days before and after; share of lines sold at the list price in effect | Point-in-time join |
| Q07 | Net revenue per worked shift hour, per employee per month | Second business process, range join |
| Q08 | Channel share of net revenue per store per month | Baseline |
| Q09 | Same-store sales growth per month versus the same month a year earlier, for stores open the whole of both months | Store lifecycle history |
| Q10 | Top 10 unordered product pairs bought in the same order, per quarter | Line grain self-join |

Layout of one question:

```
questions/q02_revenue_by_tier/
  question.yaml          # id, title, description, key columns, tolerance
  oracle.sql             # reference answer over raw landing
  kimball.sql
  3nf__core.sql
  3nf__mart.sql
  data_vault__core.sql
  data_vault__mart.sql
  obt__core.sql
  obt__mart.sql
```

Question SQL is plain DuckDB SQL, no Jinja, so it can be measured as written. For Data Vault, "core" means raw and business vault together, since PIT and bridge tables exist precisely to make the raw vault queryable.

Five hidden questions are added after the models are frozen (section 12.5).

## 8. Reference answers

- Each `oracle.sql` reads landing parquet directly and applies its own deduplication (latest version per key, voided orders removed). It never uses staging or any model, so a bug in staging cannot make all four models agree on a wrong answer.
- The oracle must work on raw landing because hidden questions and challenge questions get their oracles later, from the same data.
- The oracle itself is checked against `truth_manifest.json` (order count, daily revenue and similar invariants).
- Comparison: rows sorted by the key columns from `question.yaml`; integers compared exactly; ratios rounded to 6 decimals.
- pytest runs every question on every model and layer and fails on any mismatch. A performance number for a wrong answer is never reported.

## 9. Metrics

### 9.1 SQL complexity

Measured with sqlglot on every question file, never by hand.

- The SQL is parsed with the DuckDB dialect and pretty-printed by sqlglot first, so line counts do not depend on the author's style.
- Counted: lines, joins, CTEs, subqueries, window functions, distinct tables referenced.
- Reported per question, per model, per layer.

### 9.2 Query time

- Each model's queries run in a separate process on that model's DuckDB file only.
- `threads` and `memory_limit` are fixed and recorded.
- One warm-up run, then five timed runs. Report median, plus min and max.
- Machine spec, DuckDB version and dbt version are written into every results file.

### 9.3 Build and incremental cost

- Full build: `dbt run --full-refresh` with a selector per model. Staging is timed separately.
- Daily incremental: build up to day D-7 with `as_of_load_date`, then load the next seven days one at a time. Report median time and rows written per day. This is the real daily operating cost.

### 9.4 Storage

DuckDB file size of each model after `CHECKPOINT`, with table count and row count per layer.

### 9.5 Code size

Per model:

- Number of dbt models and files.
- Hand-written lines (non-blank, non-comment) of SQL, YAML and model-specific macros.
- Framework lines: shared macros written for the model family (the Data Vault macro library), counted separately.
- Generated lines: compiled SQL in `target/compiled`.

Hand-written lines approximate authoring effort. Compiled lines approximate what someone has to read when debugging.

## 10. Challenges

### 10.1 Mechanism

Each challenge lives in its own folder:

```
challenges/n1_1_admin_merger/
  challenge.yaml       # group, description, home-turf claims, new questions, old questions that must stay correct
  data.py              # generator extension: extra extracts after the base period, fixed seed
  questions/           # new questions with oracle.sql and per-model SQL
  solutions/
    kimball/
      models/...       # overlay: new or changed files, same paths as in warehouse/
      questions/...    # overlay for main question SQL, if it had to change
      deleted.txt      # files removed, if any
      procedure.yaml   # operational steps, for example a selective full refresh
    3nf/ ...
    data_vault/ ...
    obt/ ...
```

`museum challenge run <id>` does, for each model:

1. Copy the frozen warehouse and questions into a temporary workspace.
2. Generate the challenge data on top of the base landing.
3. Apply the overlay and compute the diff with difflib: files changed, models touched, lines added and removed, additive share (added lines over all changed lines).
4. Run `procedure.yaml` step by step, timing each step and counting rows reprocessed. This is the backfill cost.
5. Run the new questions and every old question against oracles recomputed on the extended data. Report which old questions still pass and whether their SQL had to change.

`museum challenge diff <id> <model>` prints the logical diff for review. Overlays hold full file copies, so a GitHub PR shows more lines than the real change; reviewers use this command.

Challenges are independent. Each is applied to the frozen base only.

### 10.2 Catalogue

| ID | Group | Challenge | Scope |
|---|---|---|---|
| N1.1 | Business change | Administrative merger: from 2025-07-01 provinces merge, districts disappear, only province and ward remain. A government mapping table old ward to new ward is published. Reports must work under both old and new boundaries, and history before the merger must not change | MVP |
| N1.2 | Business change | One customer can have several phone numbers (one-to-one becomes one-to-many) | post-mvp |
| N1.3 | Business change | Menu prices differ by region | post-mvp |
| N2.1 | Extension | Delivery partner app as a new source with its own customer ids. Some customers match members by normalized phone, attributes can conflict (member system wins for profile data) | MVP |
| N2.2 | Extension | Inventory and ingredients: recipes, goods receipts with unit cost, stock counts, waste. Cross-domain question: cost of goods per cup per store per month | MVP |
| N2.3 | Extension | App event log (view menu, add to cart, remove from cart, checkout), roughly ten times the volume of order lines. Funnel and abandonment questions | MVP |
| N2.4 | Extension | Branches in another country: multiple currencies, multiple time zones | post-mvp |
| G1 | Governance | Erase one customer's personal data on request, including history; aggregate answers must stay correct | MVP |
| G2 | Governance | Reproduce exactly a report exported on a past date, after late and corrected data arrived | post-mvp |

### 10.3 Governance verification

G1:

- The challenge picks a set of customers with a fixed seed and emits an erasure request.
- Each model's `procedure.yaml` holds its erasure steps.
- The verifier scans every string column of every table in the model's DuckDB file for the erased customers' PII values. The expected count is zero.
- Metrics: tables touched, rows updated or deleted, time spent, whether a rebuild was needed.
- All main questions rerun against oracles computed on the anonymized landing. Orders stay, linked to an anonymous customer, so totals do not change.
- Purging the landing archive is a shared step, reported separately.

G2 (post-mvp): the oracle for "the report as exported on date D" is the question run on landing restricted to `_load_date <= D`. Each model must reproduce it from its current state. Replaying landing is allowed, at its measured cost.

## 11. Workflow and freeze points

- Work is issue-driven: one GitHub issue, one PR. The repository owner creates issues and branches, commits, pushes, opens and merges PRs. The assistant designs, codes, tests and drafts issues, commit messages and PR descriptions in `.drafts/` (git-ignored).
- Each PR stays reviewable in one sitting, roughly under 400 changed lines excluding data and generated files.
- Major modeling decisions are recorded as short ADRs in `docs/adr/`, shipped in the PR they belong to.
- Two tags mark fairness checkpoints, both created by the owner:
  - `predictions-locked`: set when `docs/predictions.md` is merged. CI fails if the file differs from the tag.
  - `models-frozen-v1`: set when every model-building issue is merged. CI fails on any later change under `warehouse/models/` or `warehouse/macros/`. Challenges change models only through overlays.

## 12. Fairness principles

The repository is only worth something if no model is built as a straw man. Each principle below states how it is enforced.

### 12.1 Follow the canon

- `docs/checklists/{3nf,kimball,data_vault,obt}.md` hold review checklists, each item citing its source (Kimball Toolkit 3rd ed.; Linstedt and Olschimke, DV 2.0; Inmon, Building the Data Warehouse and the CIF).
- Every model-building PR fills its checklist. Each deviation from the canon is written down with its reason.

### 12.2 No anticipation

Base models serve the base requirements, built the way a competent practitioner of that model would build them. A structure that only makes sense for a specific future challenge is not allowed, for example a separate phone table while the business still has one phone per customer. A derived column is allowed only if the model's checklist lists it as standard practice. Reviewers check this in every model PR.

### 12.3 Home turf

Each model claims strengths. Each claim is tied to a metric or challenge that can confirm or refute it, and each model has at least one home-turf challenge inside the MVP.

| Model | Claimed strengths | Measured by |
|---|---|---|
| `3nf` | Integrated single source of truth, low redundancy, flexible for unforeseen questions, new subject areas fit into the integrated model | Hidden questions on the core layer; N2.2 inventory; core storage; N1.2 phone numbers (post-mvp) |
| `kimball` | Simple and fast queries, as-was and as-is through SCD2, conformed dimensions for drill-across | Complexity and time of Q01 to Q10; N1.1 admin merger; N2.2 cost per cup (drill-across sales and inventory) |
| `data_vault` | New sources are additive, full load-date audit trail, PII handled by satellite split, parallel loading | N2.1 new source (additive share); G1 erasure; G2 reproduction (post-mvp) |
| `obt` | Fewest joins, fast scans on columnar engines, fewest models, friendly for BI and ML | Presentation-layer complexity and time; N2.3 high-volume event log |

### 12.4 Pre-registered predictions

`docs/predictions.md` records, before any metric code exists, which model is expected to win each metric and challenge, and why. It is merged right after the design and checklists, earlier than the first benchmark run, because once the benchmark harness runs, numbers are visible. The file is locked by the `predictions-locked` tag. `docs/findings.md` compares every prediction with the result and explains the misses.

### 12.5 Hidden questions

- Five hidden questions measure flexibility against questions nobody prepared for.
- Their categories are fixed now: (1) grouping by an attribute no main question uses, (2) time travel to an earlier state, (3) a new many-to-many path, (4) a question across two business processes, (5) an ad-hoc question at a grain no table is built for.
- They are written only after `models-frozen-v1` exists, in their own issue that depends on the freeze issue.
- The repository owner writes the question texts, so the person who built the models does not pick questions that suit them. The assistant then writes oracles and SQL.
- Measured: answerable without changing the model or not, SQL complexity, and, if the model had to change, the same diff metrics as a challenge.

### 12.6 Fair code measurement and equal effort

- Code is split into hand-written, framework and generated (section 9.5).
- Each model may use the tools typical of it (macro libraries for Data Vault, nested types for OBT).
- Tuning is limited and equal for all: choice of materialization and sort order at build time. No question-specific aggregates, no tuning that only one model receives.

### 12.7 Real costs, many dimensions, no total score

- Costs are measured as time, rows and lines, never as yes or no.
- No metric is combined with another into a single score.
- Findings are written per situation, for example: a three-person startup with two sources; an enterprise with thirty sources and five teams; an organization under strict personal data regulation. For each situation the findings say which model fits and which numbers support that.

### 12.8 Stated limitations

See section 15. The README invites pull requests from anyone who thinks a model was built poorly.

## 13. Tooling and commands

- Python 3.11+, uv, dbt-core 1.x with dbt-duckdb, DuckDB, Faker, numpy, pyarrow, sqlglot, pytest, ruff, matplotlib for charts.
- dbt v2 (Fusion) is not used yet: its DuckDB adapter is in beta and cannot load extensions.
- One dbt project in `warehouse/`. Each model writes to its own DuckDB file under `data/<scale>/warehouse/` (attached through dbt-duckdb); staging lives in a shared file. Storage is measured per file, and the question runner attaches only the model under test, so a question cannot read another model's tables by accident. See ADR-0005.
- No Docker for the main path. A reader runs everything right after `git clone`.

Commands (the CLI is the real entry point; the Makefile wraps it for convenience, since `make` is often missing on Windows):

| Command | Does |
|---|---|
| `uv run museum generate --scale small` | Generate landing data |
| `uv run museum build --model kimball` | Build one model (or all) |
| `uv run museum verify` | Run all questions on all models and compare with oracles |
| `uv run museum bench` | Run complexity, timing, build, storage and code metrics |
| `uv run museum challenge run <id>` | Run one challenge on all models |
| `uv run museum report` | Generate `results/` tables and charts |
| `uv run museum all` (or `make all`) | Everything above in order |

CI (GitHub Actions) runs ruff, pytest, and `museum all --scale small`, plus the two tag guards.

## 14. Repository layout

```
src/museum/          Python package: cli, generator/, oracle/, questions/, metrics/, challenges/, report/
warehouse/           dbt project
  models/staging/
  models/3nf/{core,mart}/
  models/kimball/
  models/data_vault/{raw_vault,business_vault,info_mart}/
  models/obt/{intermediate,presentation}/
  macros/common/
  macros/data_vault/
questions/           q01_... to q10_..., hidden/ after the freeze
challenges/          one folder per challenge
docs/                design.md, predictions.md, findings.md, checklists/, adr/
results/             generated JSON, markdown tables and charts
tests/
data/                git-ignored: landing parquet and DuckDB files per scale
.drafts/             git-ignored: issue and PR drafts
```

## 15. Decisions, limitations and risks

### 15.1 Decision records

| ADR | Decision | Ships with |
|---|---|---|
| 0001 | SCD2 built from staging versions with window functions, not dbt snapshots. Snapshots only record history by running every day, cannot be fully refreshed, and cannot load several versions of one key in a single run | Kimball dimensions |
| 0002 | Landing is an immutable archive; rebuilds are allowed and measured | Staging |
| 0003 | In-repo Data Vault macro library, since automate_dv and datavault4dbt do not support DuckDB | Data Vault macros |
| 0004 | OBT means one wide table per business process | OBT presentation |
| 0005 | One dbt project, one DuckDB file per model | Staging |

### 15.2 Limitations of the experiment

- Simulated data. Real data is messier in ways a generator cannot fully reproduce.
- Few sources. Data Vault and Inmon are designed for many sources and many teams; this setup understates their benefits.
- Columnar engine. DuckDB favors wide scans, which helps OBT. A row-store engine might rank models differently (Postgres comparison is post-mvp).
- Immutable landing. Lets any model rebuild cheaply from raw data, which weakens Data Vault's and Inmon's history-keeping advantage.
- One builder. All four models are built by the same person and assistant, and the main questions were written by the same side. Checklists, hidden questions written by someone else, and open invitations for PRs are the mitigations.

### 15.3 Risks

| Risk | Mitigation |
|---|---|
| Generator too slow at 30 million lines | numpy batches, parallel days, performance measured early in the generator issues |
| DuckDB runs out of memory on a laptop | Fixed `memory_limit`; the `large` profile can be scaled down and the chosen size is recorded |
| Oracle and models share an author | Oracle independent of staging, checked against the truth manifest |
| Challenge PRs look larger than the change | `museum challenge diff` shows the logical diff |
| dbt moving to v2 | Versions pinned in `uv.lock`; upgrade is a separate issue |
| Scope creep | Any new work becomes its own issue draft |
