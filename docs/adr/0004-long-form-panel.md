# 0004 · Long-form panel with a dual timeline

- Status: Accepted
- Date: 2026-10-17

## Context

Factors need both per-symbol time-series context and per-timestamp
cross-sectional context. Point-in-time correctness requires distinguishing when
an event happened from when the platform could observe it.

## Decision

Use a long-form frame with one row per `(timestamp, symbol)` and numeric field
columns. Enforce these columns in `Panel`:

- `timestamp`: decision/event time used by expressions.
- `event_time`: when the underlying event occurred (defaults to `timestamp`).
- `available_at`: first time the row was observable (defaults to `timestamp`).
- `ingested_at`: platform ingestion time, optional.

`Panel.as_of(t)` filters on `available_at`. Forward-return labels are built
with an explicit execution lag and horizon using per-symbol shifts.

## Consequences

- Cross-sectional operators group by `timestamp`; time-series operators group
  by `symbol`.
- Data adapters must supply `available_at` when publication delays exist;
  otherwise the default is optimistic and is documented as such.
- Duplicate `(timestamp, symbol)` rows are rejected.
- Wide conversion is a presentation concern, not the storage contract.

## Alternatives considered

- **Wide price matrices**: fast for simple cases but poor at mixed fields,
  universes, and point-in-time metadata.
- **Event log only**: flexible, but every factor would rebuild the panel.
