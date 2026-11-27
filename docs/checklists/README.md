# Model review checklists

One checklist per model. They exist so that "is this a fair Data Vault?" becomes a review item with a source, not an opinion.

| Model | Checklist | Main sources |
|---|---|---|
| `3nf` | [3nf.md](3nf.md) | Inmon, *Building the Data Warehouse*; Inmon, Imhoff and Sousa, *Corporate Information Factory* |
| `kimball` | [kimball.md](kimball.md) | Kimball and Ross, *The Data Warehouse Toolkit*, 3rd ed. |
| `data_vault` | [data_vault.md](data_vault.md) | Linstedt and Olschimke, *Building a Scalable Data Warehouse with Data Vault 2.0* |
| `obt` | [obt.md](obt.md) | No single canon; practitioner and vendor guidance, listed in the file |

## How to use

- Every row has a status: `done`, `deviation` or `n/a`.
- `deviation` always needs a reason in the Notes column. `n/a` needs one line saying why the item does not apply.
- The PR that builds a part of a model fills in the rows for that part. Reviewers check the rows against the code.
- The freeze step requires every row of every checklist to be filled in.
- A PR that improves a model should cite the checklist row it improves, or propose a new row with a source.

## Citations

Chapter numbers refer to the editions listed in each file. Where a chapter number has not been checked against the book, the row cites the topic or section name instead. Corrections with a page reference are welcome.

## Rules shared by every model

Each checklist repeats these rows so each model gets its own status.

- **No anticipation** (design section 12.2): no structure that only serves a future challenge; every table and column is justified by the base requirements or by a checklist row; no aggregate built for a specific question; derived columns only from that model's allowed list.
- **Project rules** (design section 6): incremental build equals a full refresh; every table a question reads lives in the model's own DuckDB file; tuning is limited to materialization and sort order.
