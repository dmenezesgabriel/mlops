# Milestones (EPHEMERAL)

> **EPHEMERAL — iterates; never cited from code.** Ordered phases; steps
> reference `backlog.md` IDs. Each milestone's exit gate = repo quality
> gates green (per-package `make quality` + pre-commit) plus the
> milestone's own exit criteria. Closed phases (athena-emulator M0–M8,
> ssg site experience M9, gate-parity MQ-0…3, deep-audit MA-0…8) live in
> `docs/archive/`.

## M10 — ssg site phase 2: deferred census + mobile responsiveness (backlog §A, SX-15…22)

Goal: the `libs/ssg` built site passes a measured mobile-responsiveness
sweep and picks up the M9 census features reinstated by the user — SEO
extras, Mermaid, instant navigation, offline mode, generated social
cards, versioning, blog — benchmarked against the same two references
(`research_repos/mkdocs-material`, `research_repos/starlight`); per-feature
evidence in `prd.md` (FR-25…32). M9 cut kept: comments, analytics,
feedback widgets stay out.

Steps:
1. [x] Mobile responsiveness measure-then-fix (SX-15)
   - Evidence: `libs/ssg/tests/playwright/test_built_site_responsive.py` (13 tests); `site.css:236,254` (1rem controls), `:783` (44px floor), `:795-802` (320px compaction), `:644-648` (widget font)
2. [ ] SEO extras: twitter:* + hreflang + `x-default` + static `og:image` (SX-16)
   - Evidence: starlight `src/utils/head.ts:70,80-101,116-122`; measured absent `partials/head.html:1-25`
3. [ ] Mermaid fenced blocks (SX-17)
   - Evidence: material `docs/reference/diagrams.md:20-28`; `markdown_content_renderer.py:65-82`
4. [ ] Instant navigation (SX-18)
   - Evidence: material `docs/setup/setting-up-navigation.md:26-68`; `static/js/site.js`
5. [ ] Offline service worker (SX-19)
   - Evidence: material `src/plugins/offline/plugin.py`; `use_cases/static_site_builder.py`
6. [ ] Generated social cards (SX-20)
   - Evidence: material `src/plugins/social/`; consumes SX-16's `og:image` emission
7. [ ] Versioning (SX-21)
   - Evidence: material `docs/setup/setting-up-versioning.md:18-25` (mike)
8. [ ] Blog (SX-22)
   - Evidence: material `src/plugins/blog/` (`plugin.py`, `structure/`, `readtime/`)

**Exit criteria:** repo quality gates green for `libs/ssg` + any touched
`ssg-*` lib (`make quality`); playwright covers the 320/390/768px sweep
and the offline smoke; every feature works in both locales and degrades
without JS (site convention); G-326…G-328 closed.

## Sequence & dependencies

M10 standalone — touches `libs/ssg`(+ `ssg-*` libs where a feature needs
them) and `site/`. SX-15/SX-16 are correctness + quick wins first;
SX-19 runs after SX-18 so the service worker caches the final navigation
behavior; SX-20 and SX-21 depend on SX-16 (`og:image` emission, canonical
per-version URLs); SX-22 last — largest, self-contained.

Closed most recently: M9 → `docs/archive/ssg-site/`;
M8 → `docs/archive/athena-emulator/milestones.md`.
