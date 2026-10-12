# ADR-0004 — Type-honesty rubric

- Status: Accepted
- Date: 2026-09-26

## Context

Pyright strict is green repo-wide (QH-2), but "passes the checker" ≠ "the
signature tells the truth". Annotations written to appease the checker —
unjustified `cast()`, `Any` where a Protocol exists, `Optional` hiding
error paths — mislead the reader and rot refactoring confidence.

## Decision

Judged honest, a signature must satisfy:

- `cast()` appears only where narrowing cannot express the invariant, and
  carries a comment naming that invariant; stringized casts that hide names
  from linters (the QH-5 `evaluate.py` case) are findings.
- `Any`/`object` appear only at serialization/plugin/SDK boundaries, and
  the boundary is documented; inside the domain they are findings.
- `Optional[T]` means "the value may legitimately be absent" — not
  "sometimes None on failure" (that's a raised exception or a Result).
- Parameters take the minimal abstract type (`Iterable`, `Mapping`,
  `Protocol`); returns are concrete and complete.
- Structured payloads are `TypedDict`/`dataclass`/pydantic — not
  `dict[str, Any]`.
- No mutable default arguments; no `*args: Any, **kwargs: Any` facades
  that re-dispatch to a typed function.

## Consequences

- Audits can mechanically flag every dishonest site `file:line`.
- Fixes either tighten the type to the truth or add the invariant comment
  that makes a needed cast honest — both are small, reviewable diffs.
