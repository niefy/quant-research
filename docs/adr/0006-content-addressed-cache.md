# 0006 · Content-addressed factor cache

- Status: Accepted
- Date: 2026-10-17

## Context

Parameter sweeps and validation gates recompute the same factor many times.
A cache keyed only by factor id would return stale results after a spec or data
change, which silently corrupts research conclusions.

## Decision

Key factor artifacts by a hash of everything that affects the output:

- canonical FactorSpec document hash,
- canonical expression hash,
- resolved parameter values,
- panel fingerprint (schema, row count, content hash),
- preprocessing configuration,
- factor id/version when applicable.

Artifacts are stored as Parquet under `data/artifacts/factors/<key>.parquet`.
The cache is optional and disabled with `--no-cache`.

## Consequences

- Any input change produces a new key; stale reuse is structurally impossible.
- Repeated sweeps and gate runs reuse work without manual invalidation.
- Changing preprocessing or adapter normalization invalidates previous results,
  which is intentional.
- Cache directories need periodic pruning; this is a later operational task.

## Alternatives considered

- **mtime-based invalidation**: cheap but unreliable across copies and merges.
- **Factor-id-only cache**: fast but unsafe under parameter sweeps.
