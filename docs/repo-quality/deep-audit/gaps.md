# Gap register — Repo Deep Audit (EPHEMERAL)

> **EPHEMERAL WORK REGISTER — iterates freely; never cited from code.**
> One row per *measured* finding: the evidence, the severity, and a candidate
> fix surface so each fix lands as a small step. `AU-*` audits append rows;
> each milestone's remediation step promotes rows to `AF-*` backlog items
> (or waives them with a written reason). A row leaves the register when its
> fix ships or is waived.
>
> A suspect without a measurement lives in its `audits/AU-NN-*.md` report —
> it does not get a row here until it carries a number or a failing test
> (ADR-0001). Severities: S1 defect/vuln/race (fix before next audit) ·
> S2 measured perf/memory risk · S3 type/design/clarity debt · S4 test gap.

| ID | Pkg | File:line | Dim | Severity | Measured evidence | Candidate fix surface | Status |
|---|---|---|---|---|---|---|---|
| G-01 | mlops-shared | evaluation.py:84-85 | D1 | S1 | `calculate([1]*3,[1]*3).r2==0.0`; sklearn `r2_score` → 1.0 perfect / 0.0 wrong — impl returns 0.0 for both, perfect vs garbage indistinguishable; consumed observability-only (mlflow metrics, monitor report) | `_r2`: when `tss==0` return `1.0` if `rss==0` else `0.0` (sklearn force_finite convention) | shipped |
| G-02 | mlops-shared | logging.py:21,28-34 | D1 | S3 | `extra={"level":"SPOOFED","timestamp":"1970"}` on an ERROR record → output JSON carries spoofed `level`/`timestamp`; extras not filtered against reserved payload keys | `_extra_context`: exclude reserved payload field names | shipped |
| G-03 | mlops-shared | logging.py:33,36-37 | D1 | S3 | `extra={"run_id": object()}` absent from output — silent drop | `_extra_context`/`_is_json_scalar`: `str(value)` fallback for non-scalars | shipped |
| G-04 | mlops-shared | paths.py:14-19 | D8/D1 | S3 | `RepositoryPathResolver(/tmp/au01/repo).resolve("../../etc")` → `/tmp/etc` — escapes root; contract says repository-relative; trust boundary is repo-committed config (author error, not attacker input) | `resolve`: reject or flag non-contained results (`is_relative_to`), or document escape-by-design | shipped |
| G-05 | mlops-shared | paths.py:16-17 | D1 | S3 | `resolve("/a/../b")` → `/a/../b` unnormalized; relative branch resolves, absolute doesn't | `resolve`: `.resolve()` both branches | shipped |
| G-06 | mlops-shared | config.py:19-20 | D1 | S3 | `{1: .., "1": ..}` → `{"1": "string"}` silent collision; `on:`/`true:` YAML-1.1 keys → `"True"` | `load`: reject non-str keys instead of coercing (or detect collisions) | shipped |
| G-07 | mlops-shared | pipeline.py:43 | D1 | S3 | step whose `name` raises → RuntimeError propagates with zero log lines; started/failed pair broken | `run`: hoist `name` read or wrap the started-log line | waived |
| G-08 | mlops-shared | datasets.py:8-27 | D4 | S3 | grep: 0 implementers/consumers repo-wide; speculative protocol surface (prior QF-6 vulture triage judged params "interface contract" — vulture disposition, not a design verdict) | delete module, or keep with documented extension-point reason at triage | shipped |
| G-09 | mlops-shared | pipeline.py:32 | D4 | S3 | grep: 0 consumer subclasses (`videos` uses own port; scaffold template doesn't subclass) — only the test spy exercises it | delete `PipelineStep`, or keep with documented extension-point reason at triage | shipped |
| G-10 | mlops-shared | tests/unit/* | D9 | S4 | mutants survived: `1 - rss/tss`→`rss/tss` (r2 unasserted), `>`→`>=` boundary; uncovered: evaluation.py:26-27,85 · logging.py:20,48-50 · paths.py:17,23 · pipeline.py:46-50 | assert `r2`/`require_within` boundary; cover `configure`, step-failure, absolute-path, exc_info branches | shipped |
| G-11 | data-science-scaffold | register.py:43-56 | D1 | S3 | probes: anchors absent → `changed=False` → "already registered" (silent no-op); members anchor only → `changed=True` w/ 1/4 sites; slug present off-anchor → duplicate `projects/<slug>` member | verify each sub actually matched before writing (match counts, fail loudly); whole-array slug check instead of post-anchor lookahead | shipped |
| G-12 | data-science-scaffold | register.py:51-56 | D1 | S3 | `_insert_after_first_party_modules` subs every `  "nyc_taxi…",` line — probe: slug leaked into unrelated coverage-omit list; incidentally patched a multi-line `forbidden_modules` the dedicated fn skipped; real file safe today only because count==2 | scope subs to their TOML sections (or anchor on list headers) | shipped |
| G-13 | data-science-scaffold | template Makefile:25 | D1 | S3 | `-x` is radon `--max` not exclude: rendered `radon cc . -s -n C -x "*/node_modules/*"` → rc=0 + empty output on a tree containing an F(15) function — vacuously-green gate replicated into every generated project | `-x`→`-e` (match live `projects/*/Makefile`) | shipped |
| G-14 | data-science-scaffold | template pyproject.toml:74, Makefile | D3/D9 | S3 | template predates gate parity: `typeCheckingMode="standard"` vs repo-wide strict (all 20 pkgs post-QH-2); Makefile lacks `maintainability`(xenon)/bandit/vulture/`--cov-fail-under`; pyproject lacks `[tool.vulture]` ignores its own stubs need (`raw_directory`, `n_trials` present) | port current gate set into template Makefile + pyproject | shipped |
| G-15 | data-science-scaffold | template/hooks/pre_gen_project.py:16-18 | D1 | S3 | hook cwd = just-created `project_dir` (cookiecutter hooks.py:144 ← generate.py:381) → `cwd()/projects/<slug>` never exists; real collisions raise `OutputDirExistsException` (probe) | drop the check; keep slug validation | shipped |
| G-16 | data-science-scaffold | template `configuration.py:200-203` | D1 | S3 | rendered `ProjectConfigLoader._mapping` `str()`-coerces nested keys: `{1:a,"1":b}`→`{"1":b}`, `{True:x}`→`{"True":x}` — G-06 collision replicated at depth ≥2 (also live in `projects/*`; AX-1 candidate) | reject non-str keys in `_mapping` (mirror loader msg), or deep-validate in `YamlMappingLoader` | shipped |
| G-17 | data-science-scaffold | register.py:85-99 | D5/D1 | S3 | `main` bad slug → rc=1 + traceback (measured); usage string points at nonexistent `scripts/register_project.py`; `_assert_valid_toml` msg lacks offending detail (repo exception rule) | catch ValueError → SystemExit(msg); fix usage string; include `exc` | promoted |
| G-18 | data-science-scaffold | tests/unit/test_register.py | D9 | S4 | mutants survived: `fullmatch`→`match` (suffix-junk slugs pass), `^[a-z]`→`^[a-z0-9_]` (digit-leading passes) — rejection only tested with leading-invalid input; uncovered register.py:84-85,91-99; no anchor-drift/partial/dup/real-pyproject conformance tests | parametrize invalid slugs (`x!y`,`9abc`); anchor-drift cases; `main()` coverage; assert anchors exist in real pyproject | promoted |
| G-19 | data-science-scaffold | Makefile:18 | D1/D8 | S3 | `uvx cookiecutter` resolves floating latest vs pinned `cookiecutter==2.7.1` — render path ≠ tested path | pin `uvx cookiecutter@2.7.1`, or route recipe through workspace env / `generate()` | promoted |

## Triage

Rows are dispositioned at each milestone's remediation step; `shipped` and
`waived` rows stay as evidence (a waiver is a scoped decision, not silence).

| Row | Disposition | Item | Reason / note |
|---|---|---|---|
| G-01 | shipped | AF-01 | sklearn force_finite convention adopted 2026-09-28; regression tests cover both `tss==0` branches |
| G-02 | shipped | AF-02 | `_RESERVED_PAYLOAD_KEYS` frozenset excludes payload-owned fields; forged `level`/`timestamp`/`logger`/`exception` extras dropped 2026-09-28 |
| G-03 | shipped | AF-02 | `_json_safe` str() fallback; dict/object extras now emit stringified instead of dropping 2026-09-28 |
| G-04 | shipped | AF-03 | safe_join convention adopted 2026-09-28: join → `resolve()` → `is_relative_to` → ValueError on escape; absolute stays documented opt-out |
| G-05 | shipped | AF-03 | absolute branch now `.resolve()`d — `resolve("/a/../b")` → `/b`; shipped with G-04 |
| G-06 | shipped | AF-04 | `_require_string_key` raises ValueError naming offending key + config path; collision (`1:`/`'1':`) and YAML-1.1 bool (`on:`) keys rejected 2026-09-28 |
| G-07 | waived | — | fix surface deleted by AF-05 (`PipelineStep` removal under G-09) |
| G-08 | shipped | AF-05 | deleted `datasets.py` + pyproject vulture `ignore_names`+comment 2026-09-28; `make quality` green — 19 tests, 96.90% cov, vulture clean at min-confidence 80 without ignores |
| G-09 | shipped | AF-05 | deleted `PipelineStep` + `SpyPipelineStep` test + now-unused `abc`/`logging` imports 2026-09-28; batched with G-08 — one speculative-surface removal |
| G-10 | shipped | AF-06 | +6 tests cover RMSE reject, boundary equality, non-constant perfect r2, exc_info, configure(), root_path; both surviving mutants now killed; coverage 96.90%→100%, floor 75→95 (2026-09-28) |
| G-11 | shipped | AF-08 | verify-then-write shipped 2026-09-28: per-list slug presence → skip (heals partial registration); missing section/list/anchor → RuntimeError; probes A–C now tests |
| G-12 | shipped | AF-08 | subs scoped to `[section]` + `key` + array span — wrong-list bug class eliminated; multi-line `forbidden_modules` now extended via indent-matched splice (probe D/E tests) |
| G-13 | shipped | AF-07 | `-x`→`-e` 2026-09-28; F-probe on a rendered project: `gnarly - C (14)` now fails `make complexity` (was silent before) |
| G-14 | shipped | AF-07 | strict pyright + bandit/vulture/xenon/cov-floor 73 + `[tool.vulture]` `raw_directory`/`n_trials` ignores + `[tool.coverage.run] source=["src","tests"]` ported into template Makefile/pyproject; stub sources strict-fixed (cast ports from ml_specialization); rendered probe `make quality` green — 9 tests, 73.45% cov, pyright 0 errors (2026-09-28) |
| G-15 | shipped | AF-09 | probe + `Path` import deleted 2026-09-28; subprocess test proves it fired on the rendered tree, `OutputDirExistsException` + `FailedHookException` tests pin the real guards |
| G-16 | shipped | AF-10 | template `_mapping` rejects non-str keys via `_require_string_key` (mirrors loader msg) 2026-09-28; loader deep-validate rejected at triage — bypassable via injected `yaml_loader`, leaves coercion in place; generated `projects/*` instances still carry `str()` coercion → AX-1 sweep |
| G-17 | promoted | AF-11 | `main()` ValueError→SystemExit; fix usage string; TOML-guard message gains `exc` detail |
| G-18 | promoted | AF-12 | slug-rejection parametrization kills M1/M3; cover `main()`+TOML guard; add real-pyproject conformance test |
| G-19 | promoted | AF-13 | pin uvx to `cookiecutter@2.7.1` or route Makefile through `generate()`/workspace env |
