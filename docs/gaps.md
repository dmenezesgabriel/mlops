# Gap register (EPHEMERAL)

> **EPHEMERAL WORK REGISTER — iterates freely; never cited from code.**
> One row per *measured* finding: a benchmark number, a tracemalloc diff,
> a stress-run failure, an exploit-shaped repro, or a spec citation that
> pins the divergent behavior
> (`methodology/deep-audit/adr/0001-measured-evidence-required-for-severity.md`).
> Suspects without measurement stay in the flagging report's "Dimension
> findings" table — visible, not registered.

No open findings.

- IDs are sequential `G-NN` repo-wide — next free number is **G-326**
  (G-01…G-325 are dispositioned in `docs/archive/repo-quality/deep-audit/
  gaps.md`; athena-emulator's GP-* register is in
  `docs/archive/athena-emulator/gaps.md`).
- Severity S1–S4 + waived per
  `docs/methodology/deep-audit/methodology.md` §5; a waived row requires a
  written reason.
- A row leaves the register when its fix ships (the measured evidence
  flips) or is waived.
