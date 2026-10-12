# ADR-0003 — Measurement toolkit per claim type

- Status: Accepted
- Date: 2026-09-26

## Context

"Feels slow", "probably leaks", "might race" are the claims an audit exists
to replace. Each claim type needs a repeatable measuring instrument — and a
fallback when the code isn't runnable in isolation.

## Decision

- **Asymptotics / perf**: `timeit`/`perf_counter` around the real call at
  ≥3 input sizes (e.g. n = 10²/10³/10⁴); report times and inferred slope.
  Non-runnable internals get a dominant-loop iteration count with
  `file:line` anchors instead of a fabricated number.
- **Memory**: `tracemalloc` snapshot diff across N repeated calls, or
  object/entry-count deltas on store classes. Peak RSS probes for
  subprocess/model loads (transformers, manim).
- **Races**: threading stress harness over the shared path (≥1000 ops) or
  an explicit single-threaded-by-construction argument citing the entry
  points that establish it.
- **Security**: exploit-shaped inputs (traversal strings, malformed
  payloads, oversized inputs) run against the real parser/handler.
- **Assertion strength**: mutation spot-check — flip one branch in a core
  module and confirm some test fails; record which.
- Evidence goes in the audit report (and commit body for fixes) as numbers,
  never adjectives.

## Consequences

- Claims are reproducible — a later session can re-run the same probe.
- The toolkit is stdlib-only; no new dependencies are introduced for audit
  instrumentation.
