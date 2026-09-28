# ADR-0001 — A finding's severity requires measured evidence

- Status: Accepted
- Date: 2026-09-26

## Context

Static reading reliably produces *suspects* — code that looks wrong. Some
suspects are ghosts (dead paths, defended invariants elsewhere, intentional
trade-offs), and treating every suspect as a finding both inflates the gap
register and trains the reader to distrust it. The reverse failure is worse:
an audit that eyeballs "fine" and misses a real defect proves nothing.

## Decision

- A `gaps.md` row requires a **measurement** or a **failing test**: a
  benchmark number, a tracemalloc diff, a stress-run failure, an exploit-
  shaped repro, a mutation-check result, or a spec citation that pins the
  divergent behavior.
- Suspects without measurement are recorded in the audit report's
  "Dimension findings" table as suspects — visible, not registered.
- Severity classes (S1–S4, waived) are assigned only to measured rows.

## Consequences

- The register stays trustworthy: every row is actionable.
- Audits cost slightly more (harness work per suspect) but produce durable
  evidence — the same numbers later prove the fix.
- Reading-only observations are still captured (report table), so nothing
  is silently dropped.
