# AU-13 — videos infrastructure + CLI audit (2026-10-03)

MA-5 step 3. Target: `libs/videos` `src/videos/infrastructure/**` +
`infrastructure/cli.py` — **767 SLOC / 1004 LOC** per radon raw + wc
(17 modules; backlog said ~1600 — real surface is less than half the
estimate). Manim is absent in this env (optional `[manim]` extra) — all
`manim/*` internals measured via a fake `manim` module on `PYTHONPATH`
matching v0.20.1 `tempconfig` semantics; real-render paths marked
contract-only where noted. Gates baseline: 227 pass / 2 skipped
(`pytest.importorskip("manim")`) / 18 docker-deselected in ~2.5 s,
pyright strict 0, radon cc — `DeclarativeConceptExtension.__init__` B(6),
`StoryboardScene` B(6), `StoryboardScene.construct` B(9), all else A.
`--cov` TOTAL 84% (videos_linter pollution already registered G-149);
own-module misses measured below. Note: backlog's "renderer subprocess"
hint is stale — manim renders in-process; no subprocess exists in the
package.

## Surface inventory

| Module | SLOC | Public symbols | Entry |
|---|---|---|---|
| `infrastructure/cli.py` | 50 | `main` (entry `videos = cli:main`), `ConsoleTelemetry` | ★ `videos <id>` CLI |
| `manim/renderer.py` | 95 | `ManimRenderer` (`render`, `quality_context`), `QUALITY_MAP`/`RESOLUTION_MAP` | ← steps/pipeline; **D6/D7/D8 mandatory** |
| `manim/components.py` | 91 | `Title/Text/DiagramComponent.build`, `build_cycle/linear_nodes`, `create_target`, `register_default_components` | ← registry.build in scenes |
| `manim/scene_builder.py` | 62 | `ConfigurableScene`, `StoryboardScene` (`construct`), `ManimSceneBuilder` (`build`, `build_storyboard`) | ← steps |
| `manim/layout_engine.py` | 31 | `ManimLayoutEngine` (`apply`, `validate_placement`), `LayoutRegionCoordinates`, `REGION_MAP` | ← steps/pipeline |
| `declarative/__init__.py` | 23 | `register_all` | ★ cli |
| `declarative/discovery.py` | 11 | `find_concept_yaml_files` | ← register_all |
| `declarative/loader.py` | 13 | `yaml_to_concept_extension`, `load_concept_from_yaml_file` | ← register_all/e2e |
| `declarative/extension.py` | 30 | `DeclarativeConceptExtension` (`concept`, `create_narrative`, `scenes`) | ← loader |
| `filesystem/artifact_store.py` | 53 | `FileSystemArtifactStore` (`write_final/preview`, `resolve_output_path`, `resolve_scene_preview_path`) | ← steps/pipeline |
| `logging/structured_logger.py` | 37 | `StructuredFormatter`, `setup_structured_logging` | ★ cli |
| `validation/linter_service.py` | 25 | `LinterService` (`verify_geometry`, `verify_visuals`, `verify_video`), `LinterError` | ← cli fallback wiring |
| `validation/visual_linter.py` | 22 | `DensityAnalyzer.analyze`, `VisualLinterResult` | ← LinterService |
| `validation/geometry_rules.py` | 30 | `OverlapDetector.check_overlap` | ← LinterService |

## Callgraph

```
videos <id> [--output-dir --definitions-dir --quality]   [cli.py:36]
  ├─ setup_structured_logging() — addHandler per call   [:62 → logger:32]
  ├─ register_all(defs_dir)  ◀ OUTSIDE try              [:63]
  │   ├─ find_concept_yaml_files — non-dir → []         [discovery:8-9]
  │   ├─ load_concept_from_yaml_file → open+read        [loader:22]
  │   │   └─ yaml_to_concept_extension — safe_load      [loader:10-19]
  │   │       └─ DeclarativeConceptExtension(data)      [extension:12]
  │   │           ├─ data["concept"] → Concept.from_dict    [:13-16]
  │   │           ├─ data.get("narrative",{}).get("beats")  [:18-23]
  │   │           └─ data.get("scenes") → SceneSpec tuple   [:26-31]
  │   └─ ConceptRegistry.register(ext) — global dict    [G-141]
  ├─ ComponentRegistry + register_default_components    [:65-66]
  ├─ adapters: ManimRenderer/ManimSceneBuilder/
  │   ManimLayoutEngine/FileSystemArtifactStore(mkdir×3) [:68-71]
  ├─ try videos_linter import → LinterService fallback  [:73-80]
  ├─ Director(concept_id, adapters, linter)             [:82-90]
  └─ try: director.produce(quality)  → steps (AU-12)    [:92-99]
        └─ PreviewRenderStep: quality_context(q)        [renderer:126]
            ├─ _lock.acquire (class-level, whole yield) [:124,128]
            ├─ from manim import config — absent →      [:130-133]
            │   silent yield, lock still held
            ├─ TemporaryDirectory(manim_quality_)       [:135]
            └─ mutate global config.quality/pixel/dirs  [:146-150]
            └─ ManimRenderer.render(scene, path, q)     [:157]
                ├─ from manim import config             [:162]
                ├─ _is_temp_media_dir → substring check [:48-52,164]
                │   TRUE  → _render_to_output (no lock, [:224-232]
                │           ignores render's quality arg)
                │   FALSE → _render_in_temp_dir         [:178-210]
                │           _lock + tempconfig + dirs
                └─ _render_scene                        [:213]
                    ├─ scene.render()
                    ├─ _save_last_frame → .png side file[:55-61]
                    ├─ _find_rendered_mp4:              [:64-73]
                    │   glob("**/*.mp4") unsorted → [0]
                    │   else config.output_file (""→".")
                    └─ _copy_if_exists — silent no-op   [:76-78]
        └─ VisualValidationStep: verify_visuals(.png)   [step:26]
            ├─ DensityAnalyzer.analyze                  [visual_linter:16]
            │   └─ blank frame → bbox None → PASS       [:28-31]
            └─ verify_video(mp4) → pass (vacuous)       [linter:53-54]
        └─ FinalRenderStep → resolve_output_path        [store:45]
            └─ quality=="final" else previews/          [:46-48]
```

## Boundary table

| External boundary | Location | Fake/seam | Test |
|---|---|---|---|
| manim module (config/tempconfig/Scene/mobjects) | renderer:130,162,185; scene_builder:17,37,67; components local imports | optional extra; docker image | docker-marked only — 0 local coverage; probes used sys.path-shadow fake |
| yaml file read | loader:22-23 `open` + `safe_load` | file path arg | fixture yamls + inline strings ✓ |
| yaml shape → domain | extension:12-31 | dict injection | unit tests — but bare `except`+flag; matrix below |
| filesystem write/mkdir/copy | artifact_store:23-25,29,38; renderer copy2:78 | tmp_path dirs | artifact-store tests ✓; renderer copy arms untested locally |
| PIL image decode | visual_linter:17 `Image.open` | generated pngs | density tests ✓ (no blank-frame case) |
| `videos_linter` optional import | cli:74-80 | sys.modules patch | both arms tested via patch.dict |
| argv/stdout/stderr | cli:36-99 | `parse_args` patched in all tests | weak — no real argv, no stream asserts |
| logging stream | structured_logger:33 `StreamHandler(sys.stdout)` bound at setup | formatter unit-tested; setup() untested | partial |
| global manim config mutation | renderer:146-155 | — | docker-only |

## Dimension findings (measured)

**D1 correctness**
- `renderer.py:64-78` — `_find_rendered_mp4` takes `video_files[0]` from an
  **unsorted** `glob("**/*.mp4")` (scandir order): manim's
  `partial_movie_files/*.mp4` segments live under `media_dir` and are
  indistinguishable from the scene output; probe picked `a.mp4` first
  (reverse creation order) — selection criterion is enumeration luck, not
  finality. Fallback arms measured: `config.output_file` unset →
  `Path("") == "."` → `copy2(".")` raises `IsADirectoryError` (→ caught,
  `success=False`); pointing at an existing stale file → **copies stale
  bytes verbatim** (probe: `b'STALE'`); missing file → `_copy_if_exists`
  no-ops → `RenderResult(success=True)` **with no artifact on disk**
  (probe: `success=True, exists=False`, both via `_render_to_output` and
  `_render_in_temp_dir` paths — `_render_success` never verifies output).
  The `hasattr(config, "output_file")` guard at :68 is dead defensiveness —
  `ManimConfig` always answers the property. → **G-150**
- `renderer.py:48-52,164` — `_is_temp_media_dir` is a substring test on a
  user-controlled path. Inside `quality_context("preview")`,
  `render(quality="final")` → measured `config.quality == "low_quality"` —
  the render-time arg is silently dropped (renderer-side mechanism of
  G-126). Ambient `media_dir="/data/manim_quality_backup"` → render skips
  temp isolation entirely AND drops `quality="final"` (measured quality
  stayed `low_quality`, renders into user dir). → **G-151**
- `cli.py:62-90` vs try at :92 — `register_all`, `register_default_components`,
  adapter ctors all outside the handler: malformed yaml → **uncaught**
  `yaml.parser.ParserError` traceback; list-root yaml → uncaught `TypeError`
  (both measured via real `main()` + patched argv). Missing
  `--definitions-dir` → discovery returns `[]` silently → misleading
  `"Unknown concept 'x'. Available: []"` (measured exit(1)) instead of a
  "directory not found" error. → **G-154**
- `loader.py:18` + `extension.py:13-29` — `data: dict[str, Any]` annotated
  but unchecked; measured matrix: list root → `TypeError: 'list' indices`,
  str root → `TypeError`, missing `concept` → `KeyError: 'concept'`,
  `narrative: null` → `AttributeError: 'NoneType'.get`, `beats: 42` →
  `TypeError: 'int' not iterable`, `scenes: 42` → `TypeError`,
  `scenes: "abc"` → char-iterated → pydantic error per char. No exception
  names the file path or expected shape; `register_all` aborts the whole
  batch on the first bad file (loop at `declarative/__init__.py:21-23`
  has no per-file context). → **G-155**
- `linter_service.py:53-54` — `verify_video` is literally `pass`: measured
  `None` on missing file AND junk bytes. `VisualValidationStep` calls it
  for every existing mp4 (step:27-30) — with `videos_linter` absent (this
  env) the local fallback **silently verifies nothing** while the pipeline
  reports progress. → **G-156**
- `visual_linter.py:28-31` — all-dark frame (`30,30,30` = manim bg) →
  `mask.getbbox()` → `None` → `is_centered_only=False` → `verify_visuals`
  **passes a blank render** (measured) — precisely the failed-output case
  the check exists to catch. Arm uncovered (:29) + mutant survived (M2).
  → **G-157**
- `layout_engine.py:46-52` — `apply` unconditionally overwrites
  `props["position"]`: author-supplied `[9,9,9]` → measured `[0,3,0]`.
  Author intent silently discarded; stacking `-0.8·count` also measured
  (3.0 → 2.2 → 1.4). `REGION_MAP.get(region, origin)` at :40-41 would
  silently place unknown regions at `(0,0,0)` (masked today by the
  `LayoutRegion(comp.region)` raise at :39). → **G-159**
- `components.py:136-155` — props handled by bare `cast` + dict gets:
  `labels="abc"` → 3 single-char nodes (str iterated — measured);
  `colors=[]` → raw `ValueError: zip() argument 2 is shorter`;
  `kind="radial"` → silent cycle fallback (else arm); `rings="four"` →
  raw `ValueError` from `int()` with no spec context. → **G-160**
- `artifact_store.py:45-48` + `renderer.py:140,187` — `resolve_output_path`
  routes any non-`"final"` string to previews/ (measured `"bogus"` and
  case-mismatch `"FINAL"` → `previews/`); `QUALITY_MAP.get(q,"low_quality")`
  silently coerces garbage → low at both seams. Infra arms of the G-133
  class — distinct fix surface (produce() validation won't reach direct
  render()/resolve calls). → **G-161**

**D7 races / global state**
- `renderer.py:124` — `_lock = threading.Lock()` at **class level** +
  non-reentrant + held across `yield` at :128-153 and :191-209. Measured:
  nested `quality_context` → thread still blocked after 1 s (deadlock;
  the deadlocked thread poisons the lock for **all** `ManimRenderer`
  instances since it's class-level). Serialization across two fresh
  instances measured: `start1,end1,start2,end2` — any long-running render
  body inside `quality_context` blocks every other renderer's
  `_render_in_temp_dir`. `quality_context` also yields while holding the
  lock on the ImportError arm (:130-133) — manim-absent callers serialize
  for nothing. → **G-152**
- `structured_logger.py:32-36` — `setup_structured_logging()` does
  `addHandler` unconditionally: 3 calls → 3 handlers → one `info()` emits
  **3 identical JSON lines** (measured); `cli.main()` calls it every run →
  in-process re-runs (tests, embedders) multiply all output; handlers are
  retained for process life (D6 bounded-growth violation). `format()`
  never emits `record.exc_info` — renderer `logger.exception` produces
  `{"level","logger","message","time"}` only (measured) — tracebacks
  silently dropped under structured output; without setup, the same call
  leaks a raw traceback to stderr via root propagation. → **G-158**

**D8 security / error surface**
- Traversal at `artifact_store.py:45-53` — already registered as G-129
  (domain-side anchor + this file); re-confirmed: `resolve_scene_preview_path("../escape","s0")` → `previews/scenes/../escape_s0.mp4` escapes the scenes dir (measured).
- Raw tracebacks to stderr on yaml/constructor failures (G-154 evidence) —
  path + internals leak on a user-facing CLI.
- `yaml.safe_load` used correctly; no subprocess (backlog hint stale);
  `shutil.copy2` sources are internal paths.

**D9 tests / mutation**
- Coverage (own modules, local run): `cli.py` 94% (:28,33 ConsoleTelemetry
  arms + :103 uncovered), `extension.py` 97% (**:20 empty-beats raise
  uncovered**), `loader.py` 85% (:13-14 yaml-missing arm), `components.py`
  23%, `renderer.py` 33%, `scene_builder.py` 50% (both `construct` bodies),
  `layout_engine.py` 90% (:16 `to_list`, :74 `validate_placement` dead),
  `linter_service.py` 72% (:27-42 `verify_geometry`, :54 `verify_video`),
  `visual_linter.py` 95% (:29 blank arm).
- Shadow-copy `PYTHONPATH` mutation battery (methodology §5): **4/12
  mutants survived** —
  M1 `extension.py:19` `if not raw_beats`→`len(raw_beats)<0` SURVIVED:
  `test_rejects_missing_narrative` catches the *upstream* pydantic
  `ValidationError` on empty `metadata` via bare `except Exception`+flag —
  the guard it names is never exercised (false-positive test, matches :20
  coverage hole);
  M2 `visual_linter:28` blank-arm falsification SURVIVED (no blank test);
  M6 `cli.py:98` `file=sys.stderr`→stdout SURVIVED (no stream assertion);
  M8 `geometry_rules:24` `<=`→`<` SURVIVED — the "adjacent" test touches
  only at a *corner* (both axes separate); a true shared-edge pair is
  untested (edge-touch would count as overlap, contra the :23 comment).
  Kills: threshold `<`/`>`, stack direction, `exit(1)`, `is_centered_only`
  invert, formatter field gate, discovery sort, store quality, `id`-str arm.
- `test_cli.py` — all global `patch()`/`MagicMock`, `parse_args` patched:
  zero real-argv coverage of `main()` (ADR-0005 named-fake rule applies to
  the yaml/fs seams too — `register_all` mocked instead of a tmp defs dir).
- `test_structured_logger.py` covers the formatter only — `setup_` pileup
  and exc_info drop unasserted. `ext.scenes` asserted in unit tests but has
  **zero production consumers** (grep-verified) — tested dead surface.
  → **G-162 + G-163**

**D3/D4 design**
- `scene_builder.py:16-23` — dummy `Scene` fallback lets
  `ConfigurableScene(...)` construct without manim; `construct()` then
  raises `ImportError` at first use — deferred-failure object instead of a
  named missing-extra error (loader.py:14-16 does this correctly for yaml).
  `ManimRenderer.render()` without manim → `RenderResult(success=False)` +
  `logger.exception` carrying `ModuleNotFoundError` text — generic,
  no `videos[manim]` guidance (measured). `ManimSceneBuilder.build*` return
  `object` — hides the concrete scene contract from callers and pyright.
  → **G-153**
- Dead/vacuous surface: `DeclarativeConceptExtension.scenes` parsed+exposed,
  0 consumers; `LayoutRegionCoordinates.to_list` 0 consumers;
  `ManimLayoutEngine.validate_placement` → always `[]` (port-declared, never
  called — impl-side extends G-140); `ConfigurableScene._built_mobjects`
  accumulated, never read; `verify_geometry` impl-side also extends G-140.
  → **G-162**

**D6 memory / resources**
- Handler pileup retained for process life (G-158). `_built_mobjects`
  grows per scene construct (G-162). `TemporaryDirectory` cleanup correct
  in both render paths. No leaks in the 227-test run footprint.

**D5/D10**
- `verify_geometry` O(n²) — measured 50→1.5 ms, 100→5.7 ms, 200→22.1 ms,
  400→78.8 ms (≈quadratic); at scene scale (≤~10 components) it's bounded —
  **measured, not promoted**. Manim `tempconfig` full-state restore
  verified against v0.20.1 (`config.update(original)`) — the pixel-dim
  leak suspect from recon is **dismissed by upstream evidence**.
  `OverlapDetector` docstring semantics (touching ≠ overlap) verified —
  corner-touch probe correct; shared-edge boundary is the M8 mutant hole,
  not an impl bug. `find_concept_yaml_files` sorts — deterministic ✓.
  `ConsoleTelemetry` plain-text `print` is correct for CLI output
  (repo logging rule) — but its two methods are uncovered.

## Promoted gaps

| ID | Sev | Headline |
|---|---|---|
| G-150 | S3 | `_find_rendered_mp4` arbitrary `[0]` pick + stale-copy arm + `success=True` with no artifact |
| G-151 | S3 | `_is_temp_media_dir` substring → quality arg dropped + isolation skipped on ambient dirs |
| G-152 | S3 | class-level non-reentrant `_lock` held across yield → nested-context deadlock + global serialization |
| G-153 | S3 | manim-absent surface: silent `quality_context` yield, generic render failure, dummy-Scene deferred ImportError, `object` returns |
| G-154 | S3 | cli wiring outside try → raw tracebacks; missing defs-dir → misleading unknown-concept |
| G-155 | S3 | loader/extension raw `KeyError/TypeError/AttributeError` on malformed shapes, no file context |
| G-156 | S3 | local `LinterService.verify_video` is `pass` — pipeline's mp4 check silently vacuous |
| G-157 | S3 | blank/all-dark frame passes `verify_visuals` (`not bbox` → not centered) |
| G-158 | S3 | `setup_structured_logging` handler pileup (3 calls → 3× output) + `exc_info` dropped from JSON |
| G-159 | S3 | layout engine unconditionally overwrites author `position` prop |
| G-160 | S3 | components prop-shape mishandling: str labels→chars, `colors=[]`→ValueError, unknown kind→silent cycle, raw `int()` errors |
| G-161 | S3 | unvalidated quality coerced at infra seams (bogus→preview, case-sensitive, `.get` default) |
| G-162 | S4 | dead/vacuous infra surface: `ext.scenes`, `to_list`, `validate_placement`→`[]`, `_built_mobjects`, `object` returns, impl-side G-140 anchors |
| G-163 | S4 | mutation 4/12 survived (false-positive extension test, blank arm, stderr stream, edge-touch boundary) + all-mock CLI tests + docker-only manim coverage |

Session note: backlog LOC estimate was ~2× reality (1600 vs 767). The
"subprocess" hint was stale — manim runs in-process; the real renderer
risk class is **file-selection + false-success contract**, not process
management. Fake-manim `PYTHONPATH` shadow measured everything except the
real `Scene.render()` internals — those stay docker-contract-only, but the
selection/copy arms are plain-path functions and fully measured. No S1/S2 —
14 rows batch into MA-5 remediation with AU-11/AU-12's 33. Next: **AU-14**
`libs/videos-linter` (457 SLOC — the real `verify_video`/`verify_visuals`
implementations live there; AU-13's vacuous-fallback rows set the
comparison baseline).
