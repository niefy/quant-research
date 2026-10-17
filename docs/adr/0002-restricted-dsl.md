# 0002 · Restricted factor DSL instead of generated Python

- Status: Accepted
- Date: 2026-10-17

## Context

Agents will eventually propose factor expressions. Letting an LLM emit and
execute arbitrary Python would require a strong sandbox, is hard to audit, and
makes results depend on library internals.

## Decision

Define `FactorSpec` expressions in a small expression language:

- Python's parser is used only as a syntax front-end (`ast.parse` in `eval`
  mode); the tree is converted to our own AST and never evaluated as Python.
- Only whitelisted fields, scalar params, arithmetic/comparison operators, and
  operators in the registry are accepted.
- Params are resolved to literals before compilation, so the compiled AST is
  self-contained and hashable.
- Negative shifts and other future-looking constructs are rejected because they
  imply look-ahead bias.

## Consequences

- Every factor is statically auditable and reproducible from its canonical
  expression.
- New operators require an explicit registry entry, implementation, and tests.
- Some legitimate Python constructs (attributes, comprehensions, imports) are
  unavailable by design.
- Agents must target the DSL, not the Python runtime.

## Alternatives considered

- **`eval` in a sandbox**: smaller implementation effort, but a much larger
  security and audit surface.
- **Arbitrary Python with static analysis**: analysis is incomplete in the
  presence of dynamic imports and reflection.
