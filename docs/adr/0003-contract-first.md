# 0003 · Contract-first schemas with Pydantic v2

- Status: Accepted
- Date: 2026-10-17

## Context

The same artifacts (`FactorSpec`, `ValidationProfile`, gate reports) move
between the CLI, the API, workers, and the H5 client. Silent schema drift would
make reports incomparable and break reproducibility.

## Decision

Define versioned contracts as frozen Pydantic v2 models with
`extra="forbid"`. Export JSON Schema files into `backend/quant/contracts/schemas/`
and commit them. Hashing uses canonical JSON (sorted keys, no insignificant
whitespace, aliases applied) so the same semantic document always yields the
same hash.

## Consequences

- Unknown fields fail fast instead of being silently ignored.
- CI regenerates the schemas and fails if the committed files drift.
- Contract changes require an `apiVersion`/`version` bump and an accompanying
  migration note.
- Python and non-Python consumers share the JSON Schema as the source of truth.

## Alternatives considered

- **Plain dataclasses / dicts**: less validation and no schema export.
- **OpenAPI-first generation**: appropriate later for the HTTP layer, but the
  research kernel is not an HTTP service.
