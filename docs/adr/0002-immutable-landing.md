# ADR-0002: The landing zone is an immutable archive

Status: accepted, 2026-11-27

## Context

Every model reads the same daily extracts. Where those extracts live, and for how long, changes what a model has to do on its own:

- In classic Data Vault 2.0 and Inmon architectures the staging area is transient. Extracts are kept for a few days, and the warehouse itself is the durable store of history. A model that loses its history cannot get it back.
- In a modern lakehouse the raw layer (often called bronze) keeps every extract forever, and any downstream model can be rebuilt from it.

The choice affects the comparison directly: with a transient landing, rebuilding or restating a model is impossible, which favors models that keep full history themselves (Data Vault, the 3NF EDW) and penalizes the others.

## Decision

The landing zone keeps every extract forever and is never modified. Any model may be rebuilt from scratch at any time, and when a challenge needs a rebuild or a replay, its real cost (time, rows reprocessed) is measured and reported.

## Alternatives considered

- **Transient landing (keep N days).** Faithful to DV 2.0 and Inmon practice, but it turns "can the model rebuild?" into a yes/no that decides challenges by construction instead of by measurement.
- **Retention as a parameter, run both ways.** More complete, but it doubles every challenge run and the findings, for a question the limitations section can state in one paragraph.

## Consequences

- Rebuild costs are a measured number, not a disqualification.
- One claimed strength of Data Vault and Inmon, being the only durable store of history, is weakened. This is stated in design section 15.2 and repeated in the findings.
- Erasing personal data must also purge the landing. That step is the same for every model and is reported separately (design section 10.3).
- The landing's own storage is not counted against any model.
