# AU-19 — athena_emulator parity glue audit (2026-10-05)

MA-6 fifth and final audit item — completes the MA-6 audit sequence. Target:
`projects/athena_emulator` — **not** a workspace package (absent from root
`PACKAGES` loop + `[tool.uv.workspace] members`; no `pyproject.toml`/`Makefile`
of its own): 52+44 src SLOC of Python glue (`radon raw`: `_evidence.py` 87 LOC /
52 SLOC; `test_notebooks.py` 78 LOC / 44 SLOC) + 5 committed executed notebooks
+ generated `parity/NN_*.md` fragments and `PARITY.md`.

Environment this session: compose stack live (`athena :5001` healthy, moto
`:5000`, trino `:8485`, jupyterlab); host `.venv` has `nbformat` but **no
`nbclient`** (uv.lock carries it only under `nyc_taxi_demand_forecasting`'s
`notebooks` extra — never synced to the root dev env).

## Surface inventory

| Module | SLOC | Public symbols | Entry |
|---|---|---|---|
| `notebooks/_evidence.py` | 52 | `Evidence` :26, `EVIDENCE` :36, `record` :39, `render` :55, `persist` :67, `PROJECT_DIR` :23, (`_STATUSES` :21, `_row_line` :84) | ★ imported per-notebook (`from _evidence import persist, record, render`) |
| `tests/test_notebooks.py` | 44 | `NOTEBOOKS` :31, `ATHENA_URL` :39, `_emulator_reachable` :42, `_execute_notebook` :50, `test_notebook_runs_end_to_end` :75 | ★ pytest collection → 5 params |
| `notebooks/01…05.ipynb` | — | probe cells + `record()` calls + `persist("NN_…")` last-ish | ★ nbclient kernel per notebook |
| `parity/NN_*.md`, `PARITY.md` | — | generated artifacts (committed) | written by `persist` |

Notebook health: `nbformat.validator` 0 errors ×5; `kernelspec` `python3`
(matches `kernel_name="python3"` at test_notebooks.py:58); sequential
execution_counts from 1; all five call `persist("NN_<stem>")` matching their
filename; committed outputs present. `PARITY.md` byte-verified == `persist()`
regeneration of current fragments (89 PASS rows, 0 FAIL/GAP — the read
"drift" was a reconstruction artifact on my side: `"\n".join` inserts a blank
line `cat` doesn't).

## Callgraph

```
pytest collect (root testpaths=["libs","projects"] covers this dir) ★
  └─ module body → _emulator_reachable()                     [test_notebooks.py:42]
       └─ urllib.request.urlopen(f"{ATHENA_URL}/health", timeout=2)  [:44]
            ├─ OSError → skip marker            [:45]
            └─ NON-OSError (BadStatusLine/HTTPException) → escapes →
               COLLECTION ERROR (probe P10)

test_notebook_runs_end_to_end[NN]                            [:75] ★
  └─ _execute_notebook(name)                                 [:50]
       ├─ nbformat.read(path, as_version=4)                  [:55]
       ├─ NotebookClient(nb, kernel_name="python3", timeout=600,
       │   resources={"metadata": {"path": NOTEBOOKS_DIR}})  [:56-61]
       │   └─ lazy `from nbclient import NotebookClient`     [:52]
       │       └─ ModuleNotFoundError on host env (probe P12)
       ├─ client.execute()                                   [:62]
       │   └─ kernel (cwd=notebooks/) → notebook cells
       │        ├─ boto3/awswrangler calls → athena :5001 / moto :5000 /
       │        │   trino :8485 (live stack — not faked, by design)
       │        ├─ record(feature, status, detail, latency_ms)  [_evidence.py:39]
       │        │    └─ status guard vs _STATUSES → ValueError [:43-47]
       │        │    └─ EVIDENCE.append(Evidence(...))        [:48-51]
       │        ├─ render(rows=None→EVIDENCE) → md table      [:55-64]
       │        │    └─ _row_line: escapes `|`/`\n` in detail ONLY [:84-87]
       │        └─ persist("NN_…", rows=None→EVIDENCE)        [:67-81]
       │             ├─ parity_dir.mkdir(exist_ok=True)        [:69-70]
       │             ├─ write parity/{name}.md                 [:71-72]
       │             └─ regenerate PARITY.md from sorted(glob("*.md")) [:73-80]
       └─ nbformat.write(nb, path) — executed outputs committed back [:63]
```

Assertion depth: `client.execute()` returning is the entire test contract —
no assertion on `EVIDENCE`, fragment content, or statuses.

## Boundary table

| Boundary | Where | Faked as | Test |
|---|---|---|---|
| compose endpoints (athena/moto/trino/glue) | env `AWS_ENDPOINT_URL*` notebooks cell 1; probe :39,:44 | none — real stack | nbclient hook only |
| notebook kernel (`python3` ipykernel) | `_execute_notebook` :56-61 | none — real kernel | nbclient hook |
| filesystem writes (`parity/*.md`, `PARITY.md`, `.ipynb` outputs) | `persist` :71-80; `nbformat.write` :63 | none — writes the repo tree | nbclient hook |
| HTTP probe | `_emulator_reachable` :44 | none — real socket at import | — |
| env `AWS_ENDPOINT_URL_ATHENA` | :39 | `os.environ` seam | — |

## Dimension findings

| Dim | Suspect / measured | Evidence | Disposition |
|---|---|---|---|
| D1 | **`record(…,"FAIL",…)` rows never fail the run** — nb03 cell 11 ×3 arms, nb05 cell 29 ×4 out-of-scope probes use `"PASS" if … else "FAIL"`; nothing asserts on `EVIDENCE`. Measured end-to-end: synthetic notebook `record("x","FAIL",…)+persist` under real `NotebookClient` → `execute()` returns cleanly, `parity/00_synthetic.md` records `FAIL`, pytest contract satisfied. Converse: a mid-notebook crash skips `persist` (last-ish cell) → committed fragment keeps stale PASS rows. The parity verdict is documentation nothing enforces | synthetic nbclient run (P11) | **G-243 S4** |
| D9 | **`_evidence.py` has zero unit tests; the only test never sees its output** — mutant `render()→""` → synthetic notebook executes clean, fragment writes `## 00_synthetic` + empty table — survives. Only import-surface mutants die (kernel `ImportError` → `execute` raises); every body-level flip (status guard, escaping, glob, join) is invisible to the suite | live mutant (P-mut) | **G-244 S4** |
| D1/D8 | **`persist(name)` interpolates `name` into `parity/{name}.md` unsanitized** — `persist("../escaped")` writes `<project>/escaped.md` outside `parity/` AND the glob then omits it from `PARITY.md` (double break); `persist("a/b")` → `FileNotFoundError` (mkdir covers `parity/` only). Author-controlled today (5 literal callsites) — the contract "writes parity/<name>.md" is unenforced | /tmp-copy probes P5/P7 | **G-237 S3** |
| D1 | **`persist` indexes all fragments forever — stale sections never reconcile** — probe: plant `parity/99_orphan_from_deleted_notebook.md`, run `persist("01_fresh")` → `PARITY.md` carries the orphan section; nothing deletes fragments for renamed/deleted notebooks | /tmp probe P6 | **G-238 S3** |
| D1 | **`_row_line` escapes `detail` but not `feature`** — `record("a \| b","PASS",…)` → `| a | b | PASS | …` (5-cell row, columns shifted); `feature` `\n` splits the row. Same render path trusts unvalidated rows: `Evidence("x","BOGUS","d")` emits a bogus status (`record`'s `_STATUSES` guard lives only on the append path); `detail` non-str crashes at render, not record | /tmp probes P1/P3 | **G-236 S3** |
| D3 | **`latency_ms` rendered `{x:.0f}`** — `0.4→"0"`, `12.5→"12"` (banker's) — the column claims ms precision it discards | probe P4 | folded into G-236 |
| D6/D1 | **`EVIDENCE` is kernel-lifetime global with no reset** — re-executing a `record` cell appends a second row: EVIDENCE len 4 after one re-run → persisted fragment duplicates rows. `render()`/`persist()` default `rows=None→EVIDENCE` so there is no per-run boundary in a live Jupyter session | /tmp probe P2 | **G-240 S3** |
| D7 | **`persist` read-modify-write race** — two concurrent notebooks: A writes fragment + snapshots glob; B writes fragment + persists (index `{A,B}`); A's index write lands last from its stale snapshot → `PARITY.md` missing B's section (fragment on disk, absent from index). pytest serializes notebooks; concurrent JupyterLab kernels are the real trigger | directed interleave P9 | **G-239 S3** |
| D1/D8 | **`_emulator_reachable` probes the network at module import** — `except OSError` misses the `http.client` family: garbage-HTTP endpoint → `BadStatusLine` escapes → **collection error, not skip** (measured on a socket returning `NOT-HTTP-GARBAGE`). `timeout=2` ⇒ 2.46 s collection stall on unroutable endpoints (measured `10.255.255.1`). Non-http schemes accepted: `AWS_ENDPOINT_URL_ATHENA=file:///…` "succeeds" → tests run (bandit B310 :44, Medium/High — invisible: bandit never scans this tree, see G-245). Every bare root `pytest` pays this probe (`testpaths` covers `projects/`) regardless of `-m` | live probes P10 | **G-241 S3** |
| D5/D9 | **README's documented host run is broken today** — `uv run pytest projects/athena_emulator/tests -m integration` → 5× `ModuleNotFoundError: nbclient` (stack healthy → skipif false → lazy import at :52 dies). Only the jupyterlab-container command works. Bare `uv run pytest` at root collects these 5 (root `testpaths`) → root suite red whenever the stack is up on a host env | live run (P12): 5 failed in 0.48s | **G-242 S3** |
| D1/D9 | **Notebook inventory is convention-only** — `NOTEBOOKS` is a literal 5-name list; `pytest --collect-only` → 5 params; a 6th `.ipynb` added to `notebooks/` is silently unexecuted and unpersisted. Nothing cross-checks `glob("*.ipynb")` ↔ `NOTEBOOKS` ↔ `persist("<stem>")` literals ↔ `parity/` fragments | collect + reading | **G-247 S3** |
| D9/gov | **The glue escapes every repo gate** — not in `PACKAGES`/`uv workspace`, no own Makefile/pyproject → `make quality`/`test`/`security`/`type-check`/`complexity`/`maintainability` never touch it; only pre-commit `ruff`/`ruff-format` hook it (clean today). Manual runs: pyright (root std) 0 errors; bandit flags B310 at :44 that no gate reports; coverage `source=["libs","projects"]` traces it but nothing ever imports it → 0% invisible, no floor | Makefile/pyproject + manual gate runs | **G-245 S3** |
| D4/D5 | **Notebook helper duplication** — 10 helper names defined in ≥2 notebooks (`cleanup_run_resources`/`delete_run_buckets`/`delete_run_databases`/`object_keys_under` ×4 each; `probe_outcome`/`error_detail`/`client_error_of`/`run_workgroup_names` ×2-4). `_evidence.py` already sets the shared-sibling-import precedent; counter-argument: tutorial notebooks may be deliberately self-contained | cell census | **G-246 S3** (triage the counterpoint) |
| D1 | `sorted(parity_dir.glob("*.md"))` lexical order — correct under the `NN_` zero-pad convention (01<02<10<99 probed); only breaks at unpadded/3-digit names | P8 | suspect, no row |
| D6 | emulator resource growth per run — every notebook sweeps its prefix (nb01 last cell deletes bucket+db; nb02/03/04/05 `cleanup_run_resources`); residual growth is the state plane's (AU-21) question | cell reading | clean here |
| D7 | `EVIDENCE` cross-notebook contamination — none: nbclient spawns a fresh kernel per notebook | construction | clean |
| D8 | `nbformat.read`/`write` on committed files — repo-local trust; `file://` urlopen folded into G-241 | reading | clean apart from G-241 |
| D10 | no `features/` — surface is "notebooks execute against the live stack"; consistent with siblings, tagged for AX-2 | — | AX-2 tag |
| D2 | `persist` regenerates the index per call — O(fragments) bounded at 5; no inner loops over unbounded data | construction | clean |

## Measurements

- **collect**: `pytest --collect-only` → 5 params (literal `NOTEBOOKS` list;
  `glob("*.ipynb")` also 5 today — binding is convention, not checked).
- **render integrity** (/tmp copy): `record("a | b")` → 5-cell row;
  `record("line1\nline2")` → split row; `Evidence("x","BOGUS","d")` → renders
  BOGUS; `latency_ms=0.4→"0"`, `12.5→"12"`.
- **persist** (/tmp copy): `persist("../escaped")` → `<project>/escaped.md`
  (outside `parity/`, absent from regenerated `PARITY.md`);
  `persist("sub/dir")` → `FileNotFoundError`; planted orphan fragment
  `99_*.md` persists into `PARITY.md` across regenerations; stale-glob
  interleave → last-writer index drops the other writer's section.
- **EVIDENCE**: no reset — re-record pass duplicates rows (len 4 → dupes
  rendered + persisted).
- **probe** (`_emulator_reachable`): healthy endpoint → 200 in ~50 ms;
  unroutable `10.255.255.1` → 2.46 s at import; garbage-HTTP endpoint →
  `BadStatusLine` (NOT `OSError`) at import → pytest collection error.
- **host run (live, this session)**: `uv run pytest
  projects/athena_emulator/tests -m integration` → **5 failed** —
  `ModuleNotFoundError: nbclient` at `test_notebooks.py:52`. `uv pip list` /
  `uv.lock`: nbclient exists only as `nyc_taxi[notebooks]` extra.
- **mutation**: `render()→""` on a copy → synthetic notebook `execute()`
  clean → fragment = `## 00_synthetic` + empty table → suite stays green.
- **manual gates**: pyright (root, standard) 0 errors; ruff clean; bandit →
  1 Medium/High (B310 `urlopen` at `test_notebooks.py:44`) that no gate
  reports; zero coverage floor applies.
- **artifact sync**: `PARITY.md` == `persist()` regeneration of the 5
  fragments byte-for-byte; 89 `PASS`, 0 `FAIL`/`GAP` committed.
- **notebook health**: nbformat validation 0 errors ×5; exec counts
  sequential; all persist under their own stems.

## Gaps promoted

| Gap ID | Severity | One-line |
|---|---|---|
| G-236 | S3 | `_row_line`/`render` trust unvalidated content: `feature` unescaped (pipe/newline corrupt the table), direct `Evidence()` bypasses `_STATUSES`, `latency_ms` `:.0f` truncates, non-str detail crashes at render |
| G-237 | S3 | `persist(name)` unsanitized: `../x` escapes `parity/` (fragment lands outside AND is never indexed), `a/b` → `FileNotFoundError` |
| G-238 | S3 | `PARITY.md` indexes all `parity/*.md` forever — renamed/deleted notebooks leave orphan sections |
| G-239 | S3 | `persist` read-modify-write race — concurrent notebooks lose each other's section (stale-glob last write wins) |
| G-240 | S3 | `EVIDENCE` kernel-global never resets — cell re-execution duplicates rows into persisted fragments |
| G-241 | S3 | `_emulator_reachable` runs a network probe at collection: non-OSError (`BadStatusLine`) escapes → collection error; non-http schemes accepted; ~2.5 s stall on unroutable endpoints |
| G-242 | S3 | README host command fails today — `uv run pytest … -m integration` → 5× `ModuleNotFoundError: nbclient`; bare root `pytest` collects the same red |
| G-243 | S4 | `record(…,"FAIL",…)` never fails the run — nbclient execute is the whole contract; `PARITY.md` can carry FAIL under a green suite (and stale PASS under a red one) |
| G-244 | S4 | `_evidence.py` zero unit tests; mutant `render→""` executes clean — the suite never asserts evidence content |
| G-245 | S3 | glue escapes all gates — outside `PACKAGES`/workspace; only pre-commit ruff touches it; bandit B310 at :44 unreported; no pyright/coverage floor |
| G-246 | S3 | helper duplication across notebooks — 10 names in ≥2 (cleanup/object-keys ×4); `_helpers.py` sibling vs self-contained-tutorial triage |
| G-247 | S3 | notebook inventory is convention-only — `NOTEBOOKS` literal + per-notebook `persist("<stem>")` literal; a new `.ipynb` is silently unexecuted/unpersisted |

## Tail

- Sizing: XS held — thin surface, high probe yield (12 rows from 96 SLOC).
- Live-suite rerun not needed: committed outputs + `PARITY.md` evidence the
  last full run (Sep 26, all-PASS); all measurements were in-process or on
  synthetic notebooks — no repo-tree writes, nothing to restore.
- `PARITY.md`/fragment drift suspect died on measurement (byte-identical
  regen) — reading flagged a ghost; ADR-0001 working as intended.
- Reused verdicts: none needed (this item audits only the harness; the
  emulator itself is AU-20…AU-26).
- AX-2 tag: the notebook-execution surface (`test_notebooks.py` → live
  stack) has no bdd scenario — consistent with sibling audits.
- MA-6 note: this completes MA-6's audit sequence; its remediation step
  (42+now-12 open S3/S4 rows + pending AF-91) is the next session item
  before MA-7 athena-local planes.
