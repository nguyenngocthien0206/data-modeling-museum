# ADR-0005: One dbt project, one DuckDB file per model

Status: accepted, 2026-11-27

## Context

The four models must share one staging layer, yet be measured separately: storage per model, build time per model, and question SQL that can only see its own model's tables.

## Decision

- One dbt project in `warehouse/`, with `models/staging/` shared by all and one folder per model.
- Each model writes to its own DuckDB file under `data/<scale>/warehouse/`. Staging is the main database (`staging.duckdb`); the model files are attached as `three_nf`, `kimball`, `data_vault` and `obt`.
- A DuckDB catalog name cannot start with a digit, and dbt-duckdb does not quote catalog names, so the 3NF model's file and catalog are called `three_nf`. The model id stays `3nf` everywhere else (CLI, folders, docs).
- The question runner opens one model file on its own, so a question can only read that model. Every table a question reads must therefore be materialized in the model's own file; a view pointing back at staging would not resolve.
- `museum build` runs dbt in a child process. dbt-duckdb keeps its DuckDB connection open for the life of the process, which would lock the files against the readers that come after a build.

## Alternatives considered

- **Four dbt projects plus a shared staging package.** Clean separation, but four sets of configuration to keep in sync, and staging changes would need a package release to reach every model.
- **One DuckDB file with a schema per model.** Simpler, but storage per model would have to be estimated from internal block statistics, and nothing would stop a question from reading another model's schema.
- **dbt v2 (Fusion) with its built-in DuckDB adapter.** Still in beta and unable to load extensions; revisited in a separate decision when it matures.

## Consequences

- Storage per model is a plain file size after `CHECKPOINT`.
- Build time per model is a `dbt build` with a path selector, run in a clean process.
- Cross-database references are allowed only while building (a model reading staging); never in what a question reads.
