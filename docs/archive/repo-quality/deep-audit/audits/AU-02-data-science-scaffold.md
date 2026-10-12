# AU-02 — data-science-scaffold audit (2026-09-28)

MA-2 step 1. Package: `libs/data-science-scaffold` — project generator:
cookiecutter `template/` (renders the `projects/*` shape consumed by
AU-17/AU-18) + `register.py` (regex-rewrites root `pyproject.toml`) +
`scaffold.py` (`cookiecutter()` wrapper). 130 src LOC (radon raw; README
inventory's 152 predates recount), 161 test LOC, 6 tests, all CC = A
(avg 1.625), coverage 84.75% (floor 75), pyright strict 0 errors,
`make quality` green. No `features/` in the package itself; the template
ships `tests/bdd/test_predict.py` + `predict.feature` into generated
projects.

## Surface inventory

| Module | LOC | Public symbols | Entry |
|---|---|---|---|
| `__init__.py` | 1 | — (docstring only) | — |
| `register.py` | 103 | `register_project`, `main`★ | register.py:27,90 (`python -m data_science_scaffold.register`) |
| `scaffold.py` | 26 | `generate`, `TEMPLATE_DIR` | scaffold.py:14 (library; **zero production callers** — `grep`: only `tests/integration/test_scaffold.py:5` imports it; root Makefile:18 shells `uvx cookiecutter` directly) |
| `template/hooks/pre_gen_project.py` | 22 | `main` (hook) | cookiecutter pre_gen hook |
| `template/cookiecutter.json` | 6 | `project_slug`, `project_title`, `description`, `_copy_without_render` | vars used: slug 38×, title 6×, desc 1× — all defined, no `{%` blocks |
| `template/{{…}}/` | ~1000 rendered | generated package: `configuration.py`(243), `interfaces/cli.py`(76), `inference/*`, `pipelines/*` stubs, `tests/` | generated `cli.main` via `python -m <slug>.interfaces.cli` |

## Callgraph

```
main ─ argv ─ register_project ─ _validate_slug ─ read_text
              ─ _insert_after_members        (re.sub: MEMBER_ANCHOR + lookahead)
              ─ _insert_after_first_party_modules (re.sub: MODULE_ANCHOR + lookahead, all-sites)
              ─ _extend_forbidden_contracts  (re.sub: single-line forbidden_modules w/ nyc_taxi)
              ─ _assert_valid_toml ─ tomllib.loads ─ write_text
generate ─ cookiecutter(template=TEMPLATE_DIR, no_input, extra_context) ─►
   hooks/pre_gen_project.main ─ SLUG_PATTERN.fullmatch ─ Path.cwd()/"projects"/slug
   ─► render ~50 files under <output_dir>/<slug>
ProjectConfigLoader.load ─ YamlMappingLoader.load ─ RepositoryPathResolver
   ─ _paths/_collection/_features/_mlflow/_training/_evaluation/_feast
   ─ _mapping(str() on nested keys)/_string/_integer/_float/_integer_list
cli.main ─ MlopsLoggingConfigurator.configure ─ create_registry ─
   create_parser ─ run_command ─ registry.runner_for(cmd)(config_path)
```

Real-pyproject anchor counts (measured on `pyproject.toml`): member anchor
1× (line 45), module anchor 2× (lines 105,129 — known_first_party +
root_packages), nyc_taxi-bearing single-line `forbidden_modules` 9×.

## Boundary table

| Boundary | Where | Faked as | Test |
|---|---|---|---|
| filesystem read/write (pyproject) | register.py:30,39 | `tmp_path` file | test_register.py ✓ |
| cookiecutter render engine | scaffold.py:20 | real dep (integration) | test_scaffold.py ✓ |
| ruff subprocess on generated code | test_scaffold.py:30-31 | real binary | integration ✓ |
| process cwd inside hook | pre_gen_project.py:16 | unfaked — couples to cookiecutter hook cwd | none |
| `sys.argv` | register.py:91 | — | uncovered (91-99) |
| `uvx` network fetch + unpinned tool | Makefile:18 | unfaked, version floating | none |
| env/RNG/secrets/pickle/network in src | — none — | | |

## Dimension findings

| Dim | Suspect / measured | Evidence | Disposition |
|---|---|---|---|
| D1 | Anchors absent → `register_project` returns False → CLI prints "already registered" — silent no-op on drifted pyproject | probe A: renamed anchors → `changed=False`, 0 insertions | **G-11 S3** |
| D1 | Partial registration: members anchor present, module anchors absent → writes members only, returns True — reported success | probe B: `changed=True`, members=1, modules=0, contracts=0 | **G-11 S3** |
| D1 | Slug present but not adjacent to anchor → second copy inserted → duplicate workspace member | probe C: `members=2` after register | **G-11 S3** |
| D1 | `_insert_after_first_party_modules` subs *every* `  "nyc_taxi…",` line — probe E: slug leaked into a coverage-omit list; probe D: incidentally patched a multi-line forbidden array the dedicated `_extend_forbidden_contracts` skipped. Safe today only because count==2 | register.py:51-56; real-file count measured 2 | **G-12 S3** |
| D1 | Template radon recipe `-x` = `--max` rank filter (not `-e` exclude): rendered `make complexity` swallows the glob as max-rank → rc=0 + empty output even with an F/CC-ranked fn present — **vacuously-green gate replicated into every generated project** | rendered probe: `gnarly` F(15) invisible under `-x`, reported under `-e` | **G-13 S3** |
| D1 | `pre_gen_project.py` existence check is dead code: cookiecutter runs pre_gen hooks with cwd = the just-created `project_dir` (hooks.py:144 ← generate.py:381), so `cwd()/projects/<slug>` = `<out>/<slug>/projects/<slug>` can never exist; real collisions raise cookiecutter's `OutputDirExistsException` (probe G3) anyway | probes G2 (no spurious failure), G3 (OutputDirExistsException) | **G-15 S3** |
| D1 | Template `_mapping` re-coerces nested keys with `str()` — `{1: a, "1": b}` → `{"1": b}`, `{True: x}` → `{"True": x}`: the G-06 collision survives at depth ≥2 in generated code (top level guarded since AF-04) | probe on rendered `ProjectConfigLoader` | **G-16 S3** |
| D3 | `typeCheckingMode="standard"` in template pyproject vs repo-wide `strict` (all 20 packages since QH-2) — new projects generate below the enforced floor | diff vs `projects/*/pyproject.toml` | **G-14 S3** |
| D3 | `cast` absent; `str | Path` union honest; file-scoped `reportMissingTypeStubs=false` carries its reason (scaffold.py:3-5) | reading | clean (ADR-0004) |
| D5 | `main()` uncaught `ValueError` → rc=1 + Traceback on bad slug; stale usage `scripts/register_project.py`; `_assert_valid_toml` msg lacks offending detail (repo exception-message rule) | probes F/F2; register.py:85-87,93 | **G-17 S3** |
| D4 | `generate()` zero production callers — but it is the documented library API (README "Library API") and the pin-correct render path; Makefile duplicates it via unpinned `uvx` | grep: 1 caller (the test) | clean — earns place; see G-19 |
| D1/D8 | Makefile `uvx cookiecutter` unpinned vs package pin `cookiecutter==2.7.1` — render path ≠ tested path | Makefile:18 vs pyproject.toml:6 | **G-19 S3** |
| D2 | Three regex subs = O(file bytes), single pass each; no unbounded loops | op count | clean |
| D6 | Stateless — no stores/caches/registries retained | reading | clean |
| D7 | Non-atomic `write_text` on shared pyproject; no locking — single-shot dev tool, sequential by construction | written argument | clean (noted) |
| D8 | Slug regex `^[a-z][a-z0-9_]*$` blocks TOML/path injection (rejection tested); hook revalidates (same regex, duplicated — drift-risk noted); `$(PROJECT)` unquoted in recipe = operator-trusted make var — standard hazard | register.py:22,74; hook:5,10; Makefile:19 | clean except G-19 (suspect: make-var injection waived — operator is the caller) |
| D9 | Mutants survived: `fullmatch`→`match` (suffix-junk slugs pass), `[a-z]`→`[a-z0-9_]` (digit-leading slugs pass) — rejection tested only with leading-invalid `"Invalid-Slug"`; uncovered: register.py:84-85 (TOML guard), 91-99,103 (`main`); no anchor-drift/partial/dup/third-site/multiline/real-pyproject tests | mutation runs + coverage | **G-18 S4** |
| D9 | Mutant killed: lookahead removal → idempotency test fails | M2 | suite not vacuous |
| D10 | No `features/` — leaf dev tool; user surface = `make scaffold` covered end-to-end by integration test (render + ruff gates); register-on-real-pyproject conformance untested (folded into G-18) | find | clean |
| D1 | `_extend_forbidden_contracts` skips multi-line `forbidden_modules` (`[^\]\n]`) — latent: none exist today; incidentally covered by module-anchor sub when array items use 2-space indent (probe D) | register.py:61-63 | folded into G-12 fix surface |

Suspects not promoted (report-only): wheel build omits `template/` and
`REPO_ROOT=parents[4]` misresolves outside the checkout (measured namelist:
4 `.py` + dist-info) — no wheel-install consumer exists; workspace tool,
always run editable. `sys.argv` TOML-guard path (register.py:84-85) is
only reachable via crafted anchors — covered by G-18.

## Measurements

- Baseline: `radon raw` 130 LOC / 78 SLOC; `radon cc` 8 blocks all A,
  avg 1.625; `pytest --cov` 6 passed, 84.75% (register.py 83%:
  84-85,91-99,103); `pyright src` strict 0 errors; `make quality` green.
- Register probes (tmp pyprojects): A no-anchors→`changed=False`,0 edits;
  B members-only→`changed=True`,1/4 sites; C slug-elsewhere→2 member lines;
  D multi-line contract→0 `_extend` appends but 3 module-anchor insertions
  (incl. inside the array); E third site→slug in unrelated list; F happy
  path→1 member + 2 module + 1 contract-append.
- Hook probes: `generate("Bad Slug")`→`FailedHookException` (exit 1, hook
  stderr surfaces); cwd-collision probe→generated OK (hook cwd =
  `project_dir`, not process cwd); real output-dir collision→
  `OutputDirExistsException`.
- Rendered-project recipe: `radon cc . -s -n C -x "*/node_modules/*"` on a
  tree containing an F(15) function → rc=0, empty output; `-e` variant →
  `gnarly - C (15)` reported.
- Nested keys on rendered `ProjectConfigLoader._mapping`:
  `{1:'int','1':'str'}`→`{'1':'str'}`; `{True:'yes'}`→`{'True':'yes'}`.
- `main`: bad slug → rc=1 with traceback; no-arg → rc=1, usage string
  references nonexistent `scripts/register_project.py`.
- Wheel `data_science_scaffold-0.1.0`: namelist = 4 package files +
  dist-info — `template/` absent.
- Mutations: `fullmatch`→`match` SURVIVED (4 green); `^[a-z]`→`^[a-z0-9_]`
  SURVIVED (4 green); lookahead removal KILLED (idempotency test).

## Gaps promoted

| Gap ID | Severity | One-line |
|---|---|---|
| G-11 | S3 | anchor-absent → silent "already registered"; partial anchors → partial write reported as success; slug-off-anchor → duplicate entries |
| G-12 | S3 | module-anchor sub rewrites every `  "nyc_taxi…",` line in the file regardless of TOML section |
| G-13 | S3 | template `radon -x` recipe = vacuous complexity gate in every generated project |
| G-14 | S3 | template predates gate parity: `standard` pyright, no bandit/vulture/xenon/cov-floor, no `[tool.vulture]` ignores its stubs need |
| G-15 | S3 | pre_gen hook existence check is dead code (cwd = fresh `project_dir`); real guard is cookiecutter's `OutputDirExistsException` |
| G-16 | S3 | template `_mapping` `str()`-coerces nested YAML keys — G-06 collision replicated at depth ≥2 (also live in generated `projects/*` — see AX-1) |
| G-17 | S3 | register CLI error UX: stale usage string, traceback on bad slug, TOML-guard message lacks detail |
| G-18 | S4 | slug-validation mutants survive; `main`+TOML-guard uncovered; no anchor-drift/real-pyproject tests |
| G-19 | S3 | `uvx cookiecutter` unpinned — render path diverges from pinned `cookiecutter==2.7.1` |

Template-drift theme: G-13+G-14 are one coherent remediation diff
(port the current gate set into `template/Makefile` + template
`pyproject.toml`); kept as separate rows since each is independently
verifiable.
