# Architecture Decision Records

Short, immutable records of decisions that shape the research kernel. A new
decision supersedes an old ADR instead of editing it.

| ID | Decision | Status |
|---|---|---|
| [0001](0001-python-polars-kernel.md) | Research kernel in Python + Polars | Accepted |
| [0002](0002-restricted-dsl.md) | Restricted factor DSL instead of generated Python | Accepted |
| [0003](0003-contract-first.md) | Contract-first schemas with Pydantic v2 | Accepted |
| [0004](0004-long-form-panel.md) | Long-form panel with a dual timeline | Accepted |
| [0005](0005-staged-window-plan.md) | Staged materialization for nested windows | Accepted |
| [0006](0006-content-addressed-cache.md) | Content-addressed factor cache | Accepted |

Template:

```text
# NNNN · Title

- Status: Proposed | Accepted | Superseded by NNNN
- Date: YYYY-MM-DD

## Context
## Decision
## Consequences
## Alternatives considered
```
