# AU-08 — ssg-notebook-render audit (2026-10-01)

MA-4 step 3. Target: `libs/ssg-notebook-render` — 485 LOC / 412 SLOC per
radon raw (`notebook_content_renderer.py` 372/323, `notebook_fragment_renderer.py`
112/89, `__init__.py` 1/0); 8 tests / 402 test LOC. Gates baseline: pyright
strict 0 errors, 8 tests pass — but `pytest --cov` TOTAL is 79% over 708 stmts
because bare `--cov` traces the editable `ssg` workspace dep (no
`[tool.coverage.run] source=`); own modules measure 86% + 98%. The plugin
renders `.ipynb` pages: `NotebookContentRenderer` fans cells out to
`NotebookMarkdownRenderer` — a **verbatim copy of ssg's pre-AF-30
transclusion pipeline** — plus a Jinja-`PackageLoader` fragment renderer.
Audit weight: the copied pipeline's known defect classes (G-42/G-43/G-52),
nbformat output coverage, the widget-state embed boundary, error paths.

Reused verdicts (not re-audited): EP contract — ssg `cli.py:166-169` loads
`ssg.renderers` via `_load_plugin` + `isinstance` against
`@runtime_checkable ContentRenderer` (AU-05/AF-29); the `notebook` EP is
installed in the workspace env (`importlib.metadata` shows it) and conforms.
`ContentCollection.source_file` enforces containment (:45-57) →
`include_source("../x")` is a clean ValueError; `video_path`/`image_path`
raise ValueError naming expected keys (:59-73); `page_href` raises on unknown
slug (:75-85); duplicate case-folded basenames are rejected at config load by
`_read_asset_map` (`site_config_repository.py:178-213`, AF-30) → the G-49
overwrite class is closed for this package too — verified suspect below.
`main()` catch tuple post-AF-29: `(ValueError, TypeError, FileNotFoundError,
ImportError, RuntimeError)` at `cli.py:47-53`.

## Surface inventory

| Module | LOC | Public symbols | Entry |
|---|---|---|---|
| `notebook_content_renderer.py` | 372 | `NotebookMarkdownRenderer` (`render_markdown`★ via MarkdownRenderer port, 9 privates), `NotebookContentRenderer` (`can_render`, `render`★), `create_notebook_content_renderer`★ | `ssg.renderers` EP `notebook` (pyproject:13-14) |
| `notebook_fragment_renderer.py` | 112 | `NotebookFragmentRenderer` (9 `render_*` methods + 2 privates) | injected into both renderers |
| `__init__.py` | 1 | docstring only | — |
| `templates/*.html` | 8 files | jinja2 context vars | `PackageLoader` |

NB: `__pycache__/notebook_components.*.pyc` is a stale artifact — the module
was deleted in git history (`git log --follow` shows it gone after the
frontend extraction). Not a finding.

## Callgraph

```
(importlib.metadata EP, ssg cli.py:168)
create_notebook_content_renderer → NotebookContentRenderer()   [:371, :205]
  └─ NotebookMarkdownRenderer(NotebookFragmentRenderer())       [:214-216]

per .ipynb page — can_render: suffix == ".ipynb"               [:219]
render(collection, page, context)                               [:222]
  ├─ dependency_tracker.register_dependency(page, source_path)  [:225]
  ├─ nbformat.read(source_path, as_version=4) → cast(Any)       [:232-237]
  │     └─ validates on read: {} → ValidationError (P7);
  │        list sources joined to str (P4 dead — normalized)
  ├─ _render_cell × N                                           [:257]
  │   ├─ "markdown" → NotebookMarkdownRenderer.render_markdown  [:34]
  │   │   ├─ _render_transclusions: Environment() +             [:51-81]
  │   │   │   from_string(source).render(helpers) — FULL Jinja
  │   │   │   on author text (P1) — env built per cell (P3)
  │   │   │   ├─ _include_source → source_file → read_text      [:83]
  │   │   │   │   → frag.render_source_panel → _store_transclusion
  │   │   │   ├─ _embed_video/_embed_image → video_path/        [:103-167]
  │   │   │   │   image_path → exists-check → mkdir+copy2 →
  │   │   │   │   frag.render_*_frame → _store_transclusion
  │   │   │   └─ marker = SSG_TRANSCLUSION_{len}  (P2)          [:172]
  │   │   ├─ _render_wikilinks → page_href (ValueError caught)  [:189-202]
  │   │   ├─ MarkdownIt("commonmark").render — no table plugin  [:29,46]
  │   │   │   (P9 divergence)
  │   │   └─ _replace_transclusions + demote_top_level_headings [:177]
  │   ├─ "code" → _render_outputs → _render_output              [:272-354]
  │   │   ├─ stream → render_stream_output (list-join :313)
  │   │   ├─ data: widget-view → verbatim script (:323)
  │   │   ├─ data: text/html → verbatim (:331)
  │   │   ├─ data: image/png → _write_png_output                [:339-368]
  │   │   │     (mkdir + b64decode + write_bytes under
  │   │   │      output_path/"assets"/"images")
  │   │   ├─ data: text/plain → render_text_output (:348)
  │   │   └─ else → "" — error/jpeg/svg/json outputs dropped (P5)
  │   └─ other cell_type (raw) → ""  (nbformat: unrendered by spec)
  └─ metadata.widgets → json.dumps → <script> prepend           [:244-253]
        (no </ escaping — P6 breakout)
```

Dead-looking: none found — every private is reachable from `render`.

## Boundary table

| Boundary | Where | Faked as | Test |
|---|---|---|---|
| fs `nbformat.read` page source | :232 | real `tmp_path` ipynb | all tests |
| fs `read_text` include_source | :97 | real `tmp_path` file | transclusion tests |
| fs `mkdir`+`copy2` video/image | :127-128, :160-161 | real `tmp_path` | :83, images :57-65 |
| fs `write_bytes` png outputs | :367 | real `tmp_path` | images :157-167 |
| Jinja `from_string` on author source | :59-60 | — no seam (the defect itself) | — |
| Jinja `PackageLoader` templates | frag :10-14 | package files | :157-173 |
| `MarkdownIt("commonmark")` | :29 | real | all tests |
| `dependency_tracker` port | :92, :113, :146, :226 | never faked — `None` only | uncovered :93,:113,:146,:226 |
| `collection.source_file/video_path/image_path/page_href` | domain entities | real `ContentCollection` | implicit via asserts |
| EP loading `ssg.renderers` | ssg-side cli.py:166-169 | ssg `_load_plugin` (AF-29) | EP live-installed ✓ |
| `context.output_path` | BuildContext | real tmp dir | ✓ |

## Dimension findings

| Dim | Suspect / measured | Evidence | Disposition |
|---|---|---|---|
| D1/D8 | **Jinja-over-source executes in notebook markdown cells** — `Environment(autoescape=True, StrictUndefined).from_string(source).render(helpers)` (:59-81) runs arbitrary `{{ expr }}`/`{% stmt %}`: `{{ 7*7 }}`→`<p>49</p>`, `{{ "AB"*2 }}`→`ABAB`, `{{ [1,2,3][2] }}`→`3`, `{% set x=41 %}` executes silently; `{{ missing_name }}`→`UndefinedError` — **not** in `main()`'s catch tuple → traceback mid-build. Verbatim copy of the pipeline ssg fixed as G-42 (AF-30 regex extraction); author-trust boundary identical | :59-81; P1 | **G-72 S3** |
| D1 | **`SSG_TRANSCLUSION_{len}` markers collide with literal text** (:172): cell containing literal `SSG_TRANSCLUSION_0` + one `{{ include_source }}` → 0 marker occurrences remain, panel HTML rendered in the literal's place too (4 `source-panel` hits = 2 panels × 2 class occurrences). G-43 class | :169-187; P2 | **G-73 S3** |
| D2 | **`Environment` + `from_string` rebuilt per markdown cell** (:59-60): 0.4510 ms/cell vs 0.7257 ms for full `render_markdown` (n=500) = **62.2%** pure overhead — worse multiplier than G-52's per-page (cells ⊂ pages). AF-30 deleted the env entirely; same fix applies | timeit | **G-74 S3** |
| D1 | **`error` outputs and non-png/html/widget MIME types silently dropped** (:301-354): `output_type=="error"` has no `data` key → `""` — a cell whose run raised renders with zero output, zero signal; `image/svg+xml`, `image/jpeg`, `application/json` fall back to `text/plain` only when present (images/JSON never written). Bounded: multi-MIME outputs keep a text fallback; a sole-`image/svg+xml` output drops completely | P5 | **G-75 S3** |
| D8/D1 | **`</script>` breakout in widget-state embed** (:251-253): `json.dumps(widget_state)` interpolated raw into `<script>`; payload `"</script><b>INJECTED</b>"` survives verbatim → script element ends early, JSON remainder parses as markup (1 open / 2 close in output). Author-committed notebook boundary (G-04 convention) — but real DOM corruption + an injection shape on content that merely transits the pipeline | P6 | **G-76 S3** |
| D1 | **`nbformat` `ValidationError` escapes `main()`'s catch** → raw traceback: `{}` or `{"nbformat":4,…,"cells":"x"}` → `jsonschema.ValidationError` (MRO: Exception — not ValueError). Non-JSON → `NotJSONError` (ValueError ✓ caught); missing file → `FileNotFoundError` ✓. Malformed-but-parseable ipynb = common-enough author error → traceback | P7 | **G-77 S3** |
| D9 | **Coverage denominator polluted + floor below sibling convention**: no `[tool.coverage.run]` — TOTAL 79% over 708 stmts (~500 ssg-editable stmts incl. site.py 43%, content_collection.py 62%); own modules 86%/98%. G-68 class (AF-07 shape: `source=["src","tests"]` + floor to fit) | coverage report | **G-78 S3** |
| D1/D5 | **No GFM table support in notebook markdown** — `MarkdownIt("commonmark")` (:29) never loads the table/gfm plugin ssg's renderer enables (`markdown_content_renderer.py:27-51,72-75`): `| a | b |` in a cell renders literal pipes; site `.md` pages render tables. Author-facing inconsistency between page and cell markdown | :29; P9 | **G-79 S3** |
| D9 | **Assertion-weak suite — 10/11 mutants survived at 86% own-module coverage**: survived `can_render` `==`→`!=` (:220 uncovered), wikilink `or`→`and` (:200-202 uncovered — wikilinks never tested), stream list-join drop (:313), `widget_state`→`if True` (:248 — emits `null` script untested), missing-video raise drop (:116-118), `isinstance(data,dict)` guard (:320), `text/plain`→`text/plain-X` (:348 — data-map text/plain never asserted), frag `_render_output` escape drop (:88), `suffix.lower()` drop (:110), `title()` drop (:32). Only the markdown→code cell-type swap died. Also uncovered: dep-registration calls (:93,:113,:146,:226 — tracker never injected), missing-image raise (:149), unknown-cell `""` (:283), html list-join (:334), EP factory (:372), frag :63 | mutation run; cov | **G-80 S4** |
| D1 | cell `source` list → repr: **dead suspect** — `nbformat.read` normalizes `["a\n","b"]` → `"a\nb"` during validate-on-read (recon probe) | nbformat | closed, no row |
| D1 | video/image basename overwrite (G-49 class): **closed** — `_read_asset_map` rejects dup case-folded basenames at config load; same `source_path.name` output key as ssg's fixed renderer | site_config_repository.py:213 | closed, no row |
| D6 | growth per render — measured **bounded**: +114.5 KiB after first 200 renders (post-`gc.collect`), +27.6 KiB per next 400 → lazy caches (jinja visitor/env internals) + cyclic garbage, flattens; ~70 B/render residual amortized | tracemalloc | clean |
| D7 | shared `MarkdownIt`/`NotebookFragmentRenderer` across renders — single-threaded by construction: builder iterates pages sequentially (AU-04 callgraph); no shared counters | code path | clean |
| D3 | `cast(Any, nbformat.read)` carries the invariant comment + targeted pyright ignore (:230-237); `cast(list[str])`/`cast(dict[str,Any])` narrow under isinstance guards (:313,:321,:334,:351) — honest boundary per ADR-0004 | reading | clean |
| D4 | `MarkdownRenderer`/`NotebookFragmentRenderer` injection seams earn their place (fragment renderer is the real variance point; renderer swap is the port's purpose) | reading | clean |
| D5 | names specific; 2 modules ≤372 LOC; public surface = EP + 3 classes | reading | clean |
| D8 | `copy2`/`write_bytes` under collection/output paths (config-validated); `text/html`+widget embeds verbatim by design (author-trusted, nbconvert parity); `base64.b64decode` errors are ValueError → caught; `include_source` contained by `source_file` | reading | clean |
| D10 | no `features/`/bdd — plugin surface = `.ipynb` page builds via EP; `build` surface already AX-2-tagged (AU-04); fold notebook-page surface into AX-2 | find tests/ | folded into G-80 |

## Measurements

- **P1 (Jinja eval)**: `{{ 7*7 }}`→`<p>49</p>`; `{{ "AB"*2 }}`→`<p>ABAB</p>`;
  `{{ [1,2,3][2] }}`→`3`; `{% set x=41 %}` executes (output `kept`);
  `{{ missing_name }}`→`UndefinedError` — `isinstance(…, (ValueError,…))`
  False → escapes `main()` catch.
- **P2 (marker)**: literal `SSG_TRANSCLUSION_0` + `{{ include_source("x.py") }}`
  → `SSG_TRANSCLUSION_0` absent from output; `source-panel` count 4 = 2 panels.
- **P3 timeit**: `Environment()+from_string` 0.4510 ms vs `render_markdown`
  0.7257 ms (n=500, 1-directive source) = 62.2%.
- **P5 (output drops)**: `error` output — `ZeroDivisionError`/`tb-line-1`
  absent entirely; `image/svg+xml` → `<svg>` absent, `svg-fallback` shown;
  `image/jpeg` → image never written, `jpeg-fallback` shown; `application/json`
  → json-fallback shown; no stray files.
- **P6 (breakout)**: widget state `"</script><b>INJECTED</b>"` → verbatim in
  output inside the script element; `</script>` count 2 vs `<script` count 1.
- **P7 (error paths)**: `{}`→`ValidationError` uncaught-by-main;
  `cells:"not-a-list"`→`ValidationError` uncaught; `"not json"`→`NotJSONError`
  (ValueError ✓); missing file→`FileNotFoundError` ✓.
- **P8 (coverage)**: TOTAL 708 stmts / 79% (ssg pollution); own modules
  `notebook_content_renderer.py` 86% miss :93,:113,:116,:146,:149,:200-202,
  :220,:226,:283,:313,:320,:334,:348-354,:372; `notebook_fragment_renderer.py`
  98% miss :63; floor 75 vs sibling 95.
- **P9 (table)**: `| a | b |\n|---|---|` cell → no `<table>`, literal `| a |`.
- **P10 mutations** (ephemeral flips, reverted — `git status src/` clean):
  SURVIVED — M1 `can_render ==`→`!=`, M2 wikilink `or`→`and`, M3 stream
  list-join, M4 `if widget_state`→`if True`, M6 missing-video raise, M7
  data-dict guard, M8 `text/plain`→`text/plain-X`, F1 `_render_output`
  escape drop, F2 `suffix.lower()`, F3 `title()` drop; KILLED — M5
  `markdown`→`code` cell-type swap. 10/11 survived.
- **Wikilinks**: `[[missing-page]]` → ValueError (caught by main ✓);
  `[[x|the X page]]` → `href="x.html"` + label ✓.
- **D6 tracemalloc**: 200 renders +183.5 KiB before gc / +114.5 KiB after
  `gc.collect`; next 400 renders +27.6 KiB post-gc → bounded (jinja visitor/env
  lazy caches + cyclic garbage; ~70 B/render residual).
- **Gates baseline**: pyright strict 0 errors; 8 tests pass in 3.10s; EP
  `notebook` installed and resolvable.

## Gaps promoted

| Gap ID | Severity | One-line |
|---|---|---|
| G-72 | S3 | Jinja-over-source in notebook cells: `{{ expr }}`/`{% stmt %}` eval; `{{ undefined }}` → `UndefinedError` escapes `main()` catch (G-42 class — port AF-30's `_DIRECTIVE_PATTERN` extraction) |
| G-73 | S3 | `SSG_TRANSCLUSION_{len}` marker collides with literal text → literal replaced by panel HTML (G-43 class — `secrets.token_hex` markers) |
| G-74 | S3 | `Environment`+`from_string` rebuilt per markdown cell = 62.2% of render cost (G-52 class — regex pass deletes the env entirely) |
| G-75 | S3 | `error` outputs render as `""` (ename/traceback vanish); `image/svg+xml`/`jpeg`/`application/json` drop to `text/plain` fallback or nothing |
| G-76 | S3 | widget-state `json.dumps` embedded raw in `<script>` — `</script>` payload breaks out into DOM markup |
| G-77 | S3 | `nbformat` `ValidationError` (not a ValueError) escapes `main()`'s catch → traceback on schema-invalid ipynb |
| G-78 | S3 | no `[tool.coverage.run]` — editable `ssg` pollutes --cov (79% vs own 86/98%); floor 75 vs sibling 95 |
| G-79 | S3 | `MarkdownIt("commonmark")` lacks the table plugin ssg's renderer loads — `| a | b |` literal in cells, real tables on pages |
| G-80 | S4 | 10/11 mutants survived; uncovered: `can_render`, wikilinks, dep-registration, missing-asset raises, text/plain fallback, EP factory, frag :63; AX-2 tag for `.ipynb` page surface |

## Notes for AU-09+

- The AF-30 fix shape ports 1:1 — `_render_transclusions`/markers/env are
  verbatim copies; one `AF-*` item can carry G-72+G-73+G-74 (same diff shape
  as AF-30 minus the config-load part which already landed).
- `ssg-i18n` (AU-09) translates rendered notebook content downstream of this
  renderer — escaped-output assumptions (fragment renderer Markup handling)
  are what its translators will consume.
