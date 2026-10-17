# 0005 · Staged materialization for nested windows

- Status: Accepted
- Date: 2026-10-17

## Context

The canonical factor `cs_rank(ts_return(close, 20))` nests a window grouped by
`symbol` inside a window grouped by `timestamp`. Polars does not reliably
handle `.over("symbol")` nested inside `.over("timestamp")`; in practice the
inner expression can evaluate to all nulls without raising an error.

## Decision

Compile expressions into an ordered plan. Every grouped operation (any
operator that uses `.over(...)`) is materialized into a temporary column
(`__factor_tmp_N`), and later operations reference that column instead of
nesting the expression. Pure element-wise math and conditionals remain inline.
Temporary names are checked against reserved columns.

Execution applies plan steps sequentially with `with_columns`, so each step
sees the fully materialized output of its dependencies.

## Consequences

- Correct results for arbitrary combinations of time-series and
  cross-sectional operators.
- The plan is explicit, inspectable, and easy to test.
- Extra columns and passes increase memory/CPU modestly; this is acceptable
  relative to silent incorrectness.
- A unit test compares the staged plan against a hand-written Polars plan.

## Alternatives considered

- **Nested window expressions**: simpler plan, but produces wrong results.
- **Manual wide pivoting**: faster for some factors, but multiplies code paths
  and loses the long-form contract.
