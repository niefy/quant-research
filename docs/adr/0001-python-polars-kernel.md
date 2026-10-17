# 0001 · Research kernel in Python + Polars

- Status: Accepted
- Date: 2026-10-17

## Context

Factor evaluation is a columnar workload: for each timestamp we compute
cross-sectional statistics, and for each symbol we compute rolling statistics.
The platform also needs an ecosystem for statistics (SciPy), paper parsing, and
LLM tooling. The first implementation must stay simple enough for one developer
to run on a laptop.

## Decision

Implement the research kernel in Python 3.13 and use Polars as the execution
engine. Pandas is not used in new code. NumPy/SciPy are used only where Polars
does not expose the primitive (Spearman correlation, Newey-West standard
errors).

## Consequences

- Polars' expression API maps cleanly onto factor operators and executes
  vectorized plans.
- Grouped window operations need careful handling (see ADR 0005).
- The API/worker layer can call the same kernel in-process; no separate compute
  service is required for the first milestones.
- If a hot path outgrows Polars, it can be replaced behind the same operator
  registry without changing the DSL.

## Alternatives considered

- **Pandas**: mature but slower and weaker at grouped expressions.
- **Rust/C++ kernel**: best performance, far higher development cost for a
  single-maintainer project.
- **DuckDB SQL**: good for storage, awkward for a typed operator registry and
  per-operator unit tests.
