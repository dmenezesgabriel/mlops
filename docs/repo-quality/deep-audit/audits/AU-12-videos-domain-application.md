# AU-12 — videos domain+application audit (2026-10-03)

MA-5 step 2. Target: `libs/videos` `src/videos/domain/**` + `src/videos/application/**` —
**1592 SLOC / ~2024 LOC** per radon raw (50 modules; backlog said ~1400 — drift is
~16 one-line re-export shims + pydantic VO boilerplate, sizing holds). Excludes
`infrastructure/**` + `cli.py` (AU-13) — read only for contract evidence.
Test suite: 227 tests / 4165 LOC, `unit/` + `integration/` + `e2e/` trees +
`architecture/` tests (import-linter contracts in root pyproject:218-225:
domain ⊀ application/infrastructure, application ⊀ infrastructure). Gates
baseline: 227 pass / 2 skipped (`manim` absent — optional extra) / 18
docker-deselected in 2.3 s, pyright strict 0, radon cc clean, `pytest --cov`
TOTAL 84% — **polluted**: editable `videos_linter/linter_service.py` traced at
24% (no `[tool.coverage.run]` — G-114 class, 5th occurrence → AX-1). Production
surface: `videos <concept_id>` CLI → `register_all(yaml)` → `Director.produce`
on `videos/definition/*.yaml` (4 real concepts exercising `target`/`phase_*`
diagram rules).

## Surface inventory

| Module | SLOC | Public symbols | Entry |
|---|---|---|---|
| `application/director.py` | 79 | `Director` (`produce`; `_build_default_pipeline`) | ★ `videos` cli → `produce(quality)` |
| `application/render_pipeline.py` | 131 | `RenderPipeline` (`execute`; `_render_one_scene`, `_execute_{sequential,parallel}`, `_compile_storyboard`) | ★ library entry — **zero prod consumers** |
| `application/production_pipeline.py` | 14 | `ProductionPipeline` (`execute`) | ← Director |
| `application/pipeline_context.py` | 20 | `PipelineContext` dataclass | step carrier |
| `application/steps/*` | 211 | `NarrativePlanningStep`, `StaticValidationStep`, `PreviewRenderStep`, `VisualValidationStep`, `FinalRenderStep` (`execute`) | ← pipeline |
| `application/storyboard_planner.py` | 61 | `StoryboardPlanner` (`plan`) | ← StaticValidationStep |
| `application/component_factory.py` | 60 | `ComponentFactory` (`create_components`, `_create_*_component`) | ← planner |
| `application/components.py` | 18 | `ComponentRegistry` (`register`, `build`), `ComponentBuilder` | ← cli/ManimSceneBuilder |
| `application/use_cases/quality_gate.py` | 52 | `QualityGate` (`validate`), `ValidatorProtocol`, `RuleValidator`, `_RulesWrapper` | ← pipelines |
| `application/quality_gate.py` | 6 | re-export shim | compat |
| `application/ports/*` | 76 | `ArtifactStore`, `LayoutEngine`, `Linter`, `PipelineStep`, `Renderer`+`RenderResult`, `SceneBuilder`, `Telemetry` Protocols | injection seams |
| `domain/entities/*` | 146 | `Concept`/`ConceptId`/`ConceptTitle`/`ConceptMetadata`, `ConceptExtension`, `ConceptRegistry`+`UnknownConceptError`, `Narrative`, `Storyboard` | ← steps/loader |
| `domain/validation/*` | 254 | `TextRules`, `LayoutRules`, `TimelineRules`, `SceneRules` + 4 dup validator Protocols | ← QualityGate |
| `domain/value_objects/*` | ~380 | `SceneSpec`/`ComponentSpec`/`VisualObject`, `Timeline*` `QualityReport`/`RuleViolation`, `Layout*` `Beat`/`NarrationLine`/`BeatKind`, `StyleSpec`, `SceneId`/`QualityLevel`/`ComponentType`, presets (`layouts`, `render_profiles`, `typography`, `brand`, `transitions`) | ← everywhere |
| `domain/_base.py` | 17 | `PydanticModel` (`to_dict`, `from_dict`, `_get_adapter`) | yaml boundary |
| `domain/*.py` ×16 | ~90 | backward-compat re-export shims | dual import path |

## Callgraph

```
videos <id> [--quality]                                [cli.py:36]
  ├─ register_all(defs_dir) → yaml files →              [declarative/__init__]
  │   load_concept_from_yaml_file →                     [loader.py:22]
  │   DeclarativeConceptExtension(data) — from_dict     [extension.py:16-29]
  │   └─ ConceptRegistry.register(ext)                  [registry:31]
  │       ↳ ClassVar dict; warns+overwrites on dup
  ├─ Director(concept_id, 5 adapters, linter?)          [cli.py:82]
  │   └─ _build_default_pipeline → ProductionPipeline   [director:59]
  │       ↳ all 5 adapters REQUIRED even if pipeline=
  └─ produce(quality)  →  for step in steps: execute    [pipeline:18]
      ├─ NarrativePlanningStep                          [:11]
      │   ├─ ConceptRegistry.get(ConceptId(id))         [:12]
      │   │   ↳ UnknownConceptError → cli except → rc=1
      │   ├─ ext.create_narrative() — concept.id NOT
      │   │   checked vs concept_id (P9 → G-131)
      │   └─ correlation_id = uuid4 hex[:8]
      ├─ StaticValidationStep                           [:21]
      │   ├─ narrative None → RuntimeError (:23 uncovered)
      │   ├─ StoryboardPlanner.plan(narrative)          [planner:18]
      │   │   ├─ regions from SET → nondeterministic    [:22-27]
      │   │   │   order per PYTHONHASHSEED (P11 → G-133)
      │   │   ├─ scene_id = f"{concept.id}_beat_{i}"    [:21]
      │   │   ├─ ComponentFactory.create_components     [factory:42]
      │   │   │   ├─ title + text components
      │   │   │   └─ diagram via ClassVar rule list:    [:68-72]
      │   │   │       {"kind":…, **beat.params} — params
      │   │   │       override kind (P10 → G-132)
      │   │   └─ SceneSpec(...) — goal=text[:80]        [:57-67]
      │   ├─ QualityGate.validate(scenes)               [quality_gate:62]
      │   │   └─ 4 rule classes × rule loops            [validation/*]
      │   │       ↳ region check = enum membership,
      │   │         NOT scene.layout.regions (P7→G-129)
      │   └─ !report.passed → RuntimeError w/ details
      ├─ PreviewRenderStep                              [:31]
      │   ├─ storyboard None → RuntimeError (:33 uncov)
      │   ├─ quality_context(context.quality) — hasattr [:37-41]
      │   │   guard on DECLARED method (P1/P4 → G-125)
      │   ├─ per scene: layout.apply → build → render   [:43-53]
      │   │   scene_id=f"beat_{i}" ≠ spec.scene_id;     [:47]
      │   │   render(quality="preview") under final     [:52]
      │   │   context (P4 → G-126)
      │   ├─ !result.success → RuntimeError (:56 uncov)
      │   └─ telemetry scene_rendered per scene
      ├─ VisualValidationStep                           [:18]
      │   ├─ linter None → skip; scene_results None →
      │   │   silent skip (:20,:22 uncovered)
      │   ├─ .png sibling exists? → verify_visuals(     [:24-26]
      │   │   path, "unknown") — literal scene_id +
      │   │   side-channel .png contract (→ G-144)
      │   └─ .mp4 exists? → verify_video(path,"unknown")
      └─ FinalRenderStep                                [:35]
          ├─ quality != "final" → skip; storyboard
          │   None → SILENT skip vs preview's raise
          ├─ hasattr(build_storyboard) → protocol       [:64]
          │   `...`-body → None (P3) else fallback
          │   renders scenes[0] ONLY (P2 → G-125)
          ├─ resolve_output_path("final") → render
          └─ !success → RuntimeError (:56 uncovered)

RenderPipeline.execute(storyboard, id, quality, exec?)  [render_pipeline:42]
  ├─ own correlation_id (≠ context's)
  ├─ gate.validate → RuntimeError on fail (:55-58 uncov)
  ├─ per scene (seq or executor.submit):                [:127-141]
  │   quality_context(quality) hasattr-guarded [:77-81]
  │   store.resolve_scene_preview_path hasattr-guarded  [:85-95]
  │   → fallback via resolve_output_path+with_name
  │   (SURVIVED mutant M15 — fallback never exercised)
  ├─ result.success NEVER checked — failure recorded    [:96-109]
  │   as scene_rendered + returned (P12 → G-138)
  └─ scene id → f"{id}_{spec.scene_id}.mp4" — DOUBLES
      concept prefix vs step path (P13 → G-138)
```

Dead-looking (all grep-verified, consumers = tests only):
`RenderPipeline` whole class; `Telemetry.record_error`; `Linter.verify_geometry`
(2 impls, 0 callers anywhere incl. tests); `ArtifactStore.write_final`/
`write_preview`; `LayoutEngine.validate_placement`; VOs `SceneId`,
`QualityLevel`, `ComponentType`, `TransitionType`, `TypographyPreset`+
`DEFAULT_TYPOGRAPHY`, `BrandColors`+`DEFAULT_BRAND`, `RenderProfile`+
`BUILT_IN_PROFILES`, `LayoutPreset`+`BUILT_IN_LAYOUTS`; `MAX_BULLETS_VISIBLE`;
`PydanticModel.to_dict`/`Narrative.total_duration`/`Storyboard.
total_expected_duration`/`LayoutSpec.region_names` (test-only);
`clear_registry` conftest fixture (0 requests); `if TYPE_CHECKING: pass`
(director:26-27); `logger` bindings in 7 modules with 0 calls;
`_compile_storyboard` pass-through.

## Boundary table

| Boundary | Where | Faked as | Test |
|---|---|---|---|
| yaml → `from_dict` (pydantic ValidationError raw) | `_base.py:22-24` ← `declarative/extension.py:16-29` | real yaml strings | test_yaml_concept_files, test_loader |
| `ConceptRegistry` global ClassVar | `concept_registry.py:28` ← `register_all`, `NarrativePlanningStep` | real registry + `_extensions.clear()` private poke ×11 | most app tests |
| filesystem path joins (`concept_id`/`scene_id` → filenames) | store resolves `:45-53` ← steps/pipeline | `tmp_path` / MagicMock stores | artifact_store, linter_integration |
| `Executor` threads (port sharing) | `render_pipeline.py:127-141` | `ThreadPoolExecutor(2)` real | test_render_pipeline:112 |
| optional `videos_linter` import | `cli.py:74-80` try/ImportError | `LinterService` real | linter_integration |
| `manim` optional extra | manim/* (AU-13) | — | 2 files skip; 18 docker tests deselected |
| `PIL` image decode (verify_visuals) | `visual_linter.py` (AU-13) ← step | real PIL renders | linter_integration |
| `uuid.uuid4` correlation ids | render_pipeline:49, narrative_step:16 | — | shape-asserted (test_render_pipeline:89) |

## Dimension findings

| Dim | Suspect / measured | Evidence | Disposition |
|---|---|---|---|
| D1 | **`hasattr` guards on protocol-declared methods + `...`-body None-inheritance** — 5 sites (render_pipeline:79,85; final:43,64; preview:39). Port methods exist on the Protocols → `hasattr` True for any protocol-inheriting impl; a missing override returns `None` from the `...` body: `resolve_scene_preview_path` → `output_path=None` flows to `render`; `build_storyboard` → `full_scene=None`. G-31 class, worse — the guard can't detect nonconformance it inherits | P1+P3 | **G-125 S3** |
| D1 | **`FinalRenderStep` fallback renders `scenes[0]` only** — non-inheriting builder without `build_storyboard` → final video silently contains scene 0 of n | P2 (`calls=[s0]`, 1 render) | **G-125** (same row — the guard's harm) |
| D1 | **Preview renders execute inside the final quality context** — `quality_context(context.quality)` (:38) but `render(quality="preview")` (:52): under `--quality final`, context arg `'final'`, render arg `'preview'` ×3 — previews get final profile media-dir/settings | P4 | **G-126 S3** |
| D1 | **`QualityGate` drops `validators` when `static_rules` also passed** — elif chain; both args → only static rules run, validators silently discarded | P5 (`called=['static']`) | **G-127 S3** |
| D1 | **`unknown_layout_region` checks enum membership, not the scene's `layout.regions`** — `region="footer"` under `layout=(TITLE,)` → **no violation**; object lands in an undeclared region. Engine-side `LayoutRegion(comp.region)` (:39 infra) still catches non-enum strings | P7 | **G-128 S3** |
| D1/D8 | **`concept_id`/`scene_id` unvalidated → filesystem traversal** — `resolve_scene_preview_path("../escape","s0")` → `scenes/../escape_s0.mp4` escapes the scenes dir (`../../` reaches output root); author-yaml `concept.id` boundary (G-34 class) | P14 | **G-129 S3** |
| D1 | **Narrative identity unchecked** — extension under id `concept_a` returning `Narrative` for `concept_b` → scenes named `concept_b_beat_*`, artifacts under mismatched ids, no check anywhere | P9 | **G-130 S3** |
| D1 | **`beat.params["kind"]` overrides dispatched diagram kind** — `{"kind": "target", **params}` — `params={"kind":"cycle"}` on `visual_key="target"` emits `kind="cycle"` | P10 | **G-131 S3** |
| D1 | **`LayoutSpec.regions` order nondeterministic** — planner iterates `{"title","body","diagram"}` set → `to_dict()` differs per `PYTHONHASHSEED` (`[diagram,body,title]` vs `[diagram,title,body]`); `s1 != s2` for order-permuted equal layouts — determinism defect in a self-described deterministic engine | P11 + eq probe | **G-132 S3** |
| D1 | **`produce(quality)` unvalidated** — `produce("bogus")` runs the full preview pipeline silently; `QualityLevel` StrEnum exists, unused | P20 | **G-133 S3** |
| D1 | **Frozen VOs mutable interior** — `ComponentSpec(props)`/`Beat(params)` dict fields: `frozen=True` blocks reassignment, not mutation — `props["injected"]=…` accepted | P16 (G-100 class) | **G-134 S3** |
| D3 | **`PydanticModel.from_dict -> Any`** — declared `-> Any` (not `Self`/TypeVar); `Concept.from_dict` etc. assign `Any` into typed fields (`extension.py:16-29`) | signature + pyright | **G-135 S3** |
| D1/D3 | **`RuleViolation.actual: object` crashes `to_dict`** — `actual=object()` → `PydanticSerializationError`; `expected: str` asymmetry — annotation admits values the serializer can't emit | probe | **G-136 S3** |
| D4 | **`RenderPipeline` — zero production consumers** (cli wires `Director`; only tests instantiate) — parallel machinery incl. `Executor` path + per-call uuid correlation, kept alive by tests alone. G-123 class | grep | **G-137 S3** |
| D1 | **RenderPipeline divergent contract vs steps** — `result.success` never checked: failed renders emit `scene_rendered` telemetry and are returned (steps raise); preview naming `f"{cid}_{spec.scene_id}"` → `concept_a_concept_a_beat_0.mp4` vs step's `concept_a_beat_0.mp4` | P12+P13 | **G-138 S3** |
| D4 | **Dead VO/preset family + test-only surface** — `SceneId`, `QualityLevel`, `ComponentType`, `TransitionType`, `TypographyPreset`/`DEFAULT_TYPOGRAPHY`, `BrandColors`/`DEFAULT_BRAND`, `RenderProfile`/`BUILT_IN_PROFILES`, `LayoutPreset`/`BUILT_IN_LAYOUTS`, `MAX_BULLETS_VISIBLE`, `to_dict`, `total_duration`, `total_expected_duration`, `region_names` — zero src consumers outside re-exports; videos-linter imports only `RuleViolation`. G-08/G-123 class | grep repo-wide | **G-139 S3** |
| D4 | **Dead port methods** — `Telemetry.record_error` (0 call sites — error paths raise without telemetry), `Linter.verify_geometry` (2 impls, 0 callers incl. tests), `ArtifactStore.write_final`/`write_preview`, `LayoutEngine.validate_placement` | grep | **G-140 S3** |
| D4/D7 | **`ConceptRegistry._extensions` ClassVar global singleton** — docstring admits "Thread-unsafe"; `register_all`↔step global seam violates the repo DI rule; no `clear()` — tests poke `_extensions` ×11; bounded by registered ids (P22: overwrite keeps size flat — warns, allows) | reading + grep + P22 | **G-141 S3** |
| D4/D7 | **`ComponentFactory._diagram_rules` ClassVar mutable + lazy `_init_diagram_rules`** re-entered per `create_components` call — a module constant expresses the same thing without the init dance | reading | **G-142 S3** |
| D4/D3 | **Director API honesty** — `__init__` requires all 5 adapters even when `pipeline=` injected (`TypeError` missing 5 args, P8); `produce()` returns `None` — discards the context carrying `final_result` (unreachable through the public path) | P8 + reading | **G-143 S3** |
| D1/D5 | **VisualValidationStep** — literal `"unknown"` scene_id though real ids are zippable from `context.storyboard`; `.png`-sibling side-channel contract on `RenderResult` undocumented; missing artifacts → silent skip (a renderer producing nothing passes "visual validation"); `:20,:22,:28` uncovered | reading + P8-style stub run | **G-144 S3** |
| D4/D5 | **Ceremonial cluster** — 5 identical callable validator Protocols (`{Layout,Timeline,Text,Scene}RuleValidator` + `RuleValidator`) vs `ValidatorProtocol`+`_RulesWrapper` dual shape; protocols live in `use_cases/` not `ports/`; dead `if TYPE_CHECKING: pass` (director:26); 7 `logger` bindings, 0 calls; `_compile_storyboard` pass-through; `Narrative`/`Storyboard` plain classes among pydantic VOs; dual correlation_id sources | grep + reading | **G-145 S3** |
| D1 | **`ComponentRegistry.register` silent overwrite** — duplicate `type_name` → last wins, no warning (unlike ConceptRegistry which warns) | probe (`second` wins) | **G-146 S3** |
| D5 | **Shim-vs-canonical import split** — `src/`: 43 shim-path vs 47 canonical imports; tests: 38 shim vs 6 canonical; `videos_linter` consumes shim path — "import from canonical location instead" comment inverted by practice | grep counts | **G-147 S3** |
| D1 | **`SceneSpec` goal-validator message interpolates the empty value, not the scene** — `goal must not be empty for scene '   '` | P6 | **G-148 S3** |
| D9/D10 | **Test-quality bundle** — TOTAL 84% polluted (videos_linter 24%, no `[tool.coverage.run]`; own modules: factory 88%, render_pipeline 93%, steps 90-95%); mutants SURVIVED 4/20: M2 `>`→`>=` duration boundary, M4 `>`→`>=` word boundary, M11 `if matches`→`if not matches` (diagram presence unasserted on real yaml beats), M15 `hasattr`→`False` (store fallback never exercised); `test_execute_rejects_empty_storyboard` pins `Storyboard` ctor not the pipeline (wrong layer); MagicMock mix (extension/linter/`spec=ArtifactStore`) + `artifact_store._tmp` poke + `_extensions` pokes ×11 vs dead `clear_registry` fixture (ADR-0005); no `features/` — `videos` CLI surface → AX-2 | cov + mutation run | **G-149 S4** |
| D1 | `TimelineSpec` strictly-increasing rejects simultaneous events (two objects at t=1.0) — documented invariant in the error text; restrictive-by-design, no demonstrated harm | probe | suspect, no row |
| D1 | `FinalRenderStep` storyboard-None silent return vs PreviewRenderStep's RuntimeError — unreachable under step ordering; inconsistent contract | reading | suspect, no row |
| D1 | `goal=beat.narration.text[:80]` mid-word/newline truncation | reading | suspect, no row |
| D7 | `_execute_parallel` shares ports across threads — no declared thread-safety contract; latent while RenderPipeline is production-dead; sequential-by-construction in the Director path | construction | suspect, no row |
| D6 | registries/stores bounded — `_extensions` flat across overwrite cycles (P22); `_diagram_rules` fixed 2; `_adapter` per-subclass | P22 | suspect, no row |
| D2 | nested validate loops linear; `sorted(known)` per violation bounded; `Storyboard.scenes` tuple-copy per access bounded; `all_region_names()` per beat O(8) | reading | clean |
| D7 | Director path single-threaded by construction (sequential `execute`); ConceptRegistry docstring admits thread-unsafety — only writer is `register_all` pre-fork at cli start | construction | clean (G-141 covers the seam) |
| D8 | `LayoutRegion(comp.region)` ValueError on non-enum region — caught upstream by the gate's `unknown_layout_region`; pydantic rejects `ConceptId(123)` (string_type), coerces `time_seconds="2"`→2.0 | probes | clean |
| D1 | `QualityReport` invariant enforced (passed+violations rejected, failed-no-violations rejected); `Narrative` OPENING/RECAP invariants; `Storyboard` dup-scene rejection; `UnknownConceptError`/`LookupError` messages name value+set | probes | clean |

## Measurements

- **Coverage**: `pytest --cov` TOTAL 84% / 3705 stmts — includes tests +
  `videos_linter` editable dep (24%, 231 stmts dragged in via cli's optional
  import). Own-module: component_factory 88% (:28,:36,:50,:72),
  render_pipeline 93% (:55-58,:90-93), final_render_step 90% (:39,:56,:68),
  preview_render_step 94% (:33,:56), static_validation 95% (:23),
  visual_validation 90% (:20,:28), text_rules 97% (:59); domain VOs/entities
  ~100%.
- **P1 None-inheritance**: `StubArtifactStore(ArtifactStore)` sans override →
  `hasattr=True`, call → `None`; `BuilderMissing(SceneBuilder).
  build_storyboard` → `None`; `R(Renderer).quality_context` → real default
  `nullcontext()`.
- **P2 scenes[0] fallback**: duck-typed builder (no `build_storyboard`) on
  3-scene storyboard → `build` called once with `s0`; 1 render total.
- **P3 None full_scene**: protocol-inheriting builder sans override →
  `render` receives `scene_job=None`.
- **P4 context/render mismatch**: `produce`-style final run →
  `quality_context('final')` ×1, `render(quality='preview')` ×3.
- **P5 elif drop**: both kwargs → `called == ['static']` (validators' validate
  never invoked).
- **P6**: `SceneSpec(goal=" ")` → `goal must not be empty for scene ' '`.
- **P7**: `region="footer"` + `layout=(TITLE,)` → `violations == []`;
  `region="bogus"` → `['unknown_layout_region']`.
- **P8**: `Director("c", pipeline=…)` → `TypeError: missing 5 required
  positional arguments`.
- **P9**: ext `concept_a` → `create_narrative` for `concept_b` → scene_ids
  `['concept_b_beat_0','concept_b_beat_1']`.
- **P10**: `Beat(visual_key="target", params={"kind":"cycle"})` → emitted
  `kind="cycle"`.
- **P11**: planner `regions` order across PYTHONHASHSEED 0/1/2 →
  `[diagram,body,title]` / `[diagram,title,body]` × 2; `to_dict` identical
  variance; `LayoutSpec((title,body)) != LayoutSpec((body,title))`.
- **P12**: `RenderResult(success=False)` → RenderPipeline returns it +
  `scene_rendered` telemetry; `PreviewRenderStep` raises `RuntimeError` on the
  same result.
- **P13**: `concept_a_concept_a_beat_0.mp4` (pipeline) vs
  `concept_a_beat_0.mp4` (step).
- **P14**: `resolve_scene_preview_path("../escape","s0")` →
  `<root>/previews/scenes/../escape_s0.mp4`.
- **P16**: `frozen=True` VO — `props["injected"]="yes"` / `params["added"]=1`
  both accepted.
- **P17**: `TimelineEvent(1.0)+TimelineEvent(1.0)` → rejected (documented).
- **P19**: `ConceptId(123)` rejected; `time_seconds="2"` → `2.0` (lax coerce).
- **P20**: `produce(quality="bogus")` — full pipeline ran, no error.
- **P22**: registry 5→5 across re-registration (warns `Overwriting
  extension`); bounded.
- **Serialization**: `RuleViolation(actual=object()).to_dict()` →
  `PydanticSerializationError`; `actual={1,2,3}` → `[1,2,3]` (set→list).
- **Dup register**: `ComponentRegistry.register("title", first)` then
  `("title", second)` → `build` → `second` (silent).
- **Mutation run** (copytree + `PYTHONPATH` shadow, suite = 227 tests, 20
  flips): SURVIVED — M2 `time_seconds > dur`→`>=` (exact-duration boundary),
  M4 `> MAX_WORDS`→`>=` (14-word boundary), M11 `if matches`→`if not matches`
  (diagram presence unasserted on `target`/`phase_*` real beats), M15
  `hasattr`→`False` (store-fallback path never exercised); KILLED — M1
  region-empty, M3 `not in` object_ids, M5 title-check, M6 gate-raise, M7
  quality flip, M8 success-check, M9 OPENING check, M10 dup-scene, M12
  `<=0`→`<0` duration, M13 `<0`→`<=0` time, M14 context-guard, M16
  build_storyboard-guard, M17 static_rules guard, M18 violations flip, M19
  `<=`→`<` increasing, M20 linter-guard flip. **4/20 survived.**
- **Gates** (clean at HEAD): pyright strict 0, ruff clean, radon cc no C+,
  bandit/vulture silent, xenon clean; import-linter contracts pass.

## Gaps promoted

| Gap ID | Severity | One-line |
|---|---|---|
| G-125 | S3 | `hasattr` guards on port-declared methods + `...`-body None-inheritance — `output_path=None`/`full_scene=None`/`scenes[0]`-only final silently (5 sites) |
| G-126 | S3 | PreviewRenderStep enters `quality_context(context.quality)` but renders `quality="preview"` — previews run under final profile |
| G-127 | S3 | `QualityGate(static_rules=…, validators=…)` — elif silently drops `validators` |
| G-128 | S3 | `unknown_layout_region` checks enum membership, not the scene's `layout.regions` — enum-valid undeclared region passes |
| G-129 | S3 | `concept_id`/`scene_id` unvalidated → `../` escapes `FileSystemArtifactStore` joins |
| G-130 | S3 | `NarrativePlanningStep` never checks `narrative.concept.id == concept_id` — mismatched extension yields wrong-named artifacts |
| G-131 | S3 | `beat.params["kind"]` overrides the dispatched diagram kind in `{"kind":…, **params}` |
| G-132 | S3 | planner builds `LayoutSpec.regions` from a set — order/`to_dict`/equality vary per `PYTHONHASHSEED` |
| G-133 | S3 | `produce(quality)` unvalidated — `"bogus"` runs the preview pipeline silently; `QualityLevel` unused |
| G-134 | S3 | `ComponentSpec.props`/`Beat.params` mutable dicts inside `frozen=True` VOs |
| G-135 | S3 | `PydanticModel.from_dict -> Any` — `Any` assigned into typed fields at the yaml boundary |
| G-136 | S3 | `RuleViolation.actual: object` — `to_dict()` `PydanticSerializationError` on non-scalar |
| G-137 | S3 | `RenderPipeline` zero production consumers — parallel machinery alive only in tests |
| G-138 | S3 | RenderPipeline ignores `result.success` + preview naming `{c}_{c}_beat_0` vs step's `{c}_beat_0` |
| G-139 | S3 | dead VO/preset family + test-only surface (~12 symbols) — zero src consumers |
| G-140 | S3 | dead port methods — `record_error`, `verify_geometry`, `write_final`, `write_preview`, `validate_placement` |
| G-141 | S3 | `ConceptRegistry._extensions` ClassVar global — thread-unsafe seam, DI violation, no `clear()` |
| G-142 | S3 | `ComponentFactory._diagram_rules` ClassVar mutable + per-call lazy init — module constant suffices |
| G-143 | S3 | `Director` requires all adapters with injected `pipeline`; `produce()` discards `final_result` context |
| G-144 | S3 | VisualValidationStep — `"unknown"` scene_id, silent-skip on missing artifacts, undocumented `.png` side-channel |
| G-145 | S3 | ceremonial cluster — 5 dup validator Protocols, `_RulesWrapper`, dead `TYPE_CHECKING`/`logger`×7/`_compile_storyboard` |
| G-146 | S3 | `ComponentRegistry.register` silent last-wins overwrite on duplicate `type_name` |
| G-147 | S3 | shim-vs-canonical import split — "canonical location" convention inverted by practice (43/47, 38/6) |
| G-148 | S3 | `SceneSpec` goal-error message interpolates the empty goal, not the `scene_id` |
| G-149 | S4 | coverage pollution + own-module misses; 4/20 mutants survived; MagicMock/fixture violations; no `features/` → AX-2 |

Session note: backlog item accurate as written — the `hasattr`+`...`-body
interaction (P1/P3) is a richer variant of the G-31 duck-typing class:
protocols-as-base-classes make `hasattr` proofs vacuous AND inject silent-`None`
defaults; worth an AX-1 sweep pattern (`hasattr` on declared members). The
`TimelineSpec` strictly-increasing invariant and `FinalRenderStep` silent-skip
stayed suspects (documented intent / unreachable under ordering). No S1/S2 —
all 24 rows batch into the MA-5 remediation step. Mutation harness: copytree +
`PYTHONPATH` shadow (editable `.pth` loses to `PYTHONPATH`) — cleaner than
AU-11's symlink attempt. Next: **AU-13** `libs/videos` infrastructure + CLI
(~1600 LOC; `manim/renderer` subprocess+temp files — D6/D7/D8 mandatory;
manim absent in this env → contract-only for render internals).
