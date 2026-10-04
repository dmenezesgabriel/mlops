# AU-14 — videos-linter audit (2026-10-03)

MA-5 final audit item. Target: `libs/videos-linter` — **456 LOC / 378 SLOC**
in ONE module `src/videos_linter/linter_service.py` + 1-line `__init__.py`
(backlog 457 holds). Test suite: 14 tests / 335 LOC / 5 files, AAA-shaped,
2.3 s. Gates baseline: 14 pass, pyright strict 0 errors, radon cc clean,
vulture clean, `pytest --cov` TOTAL 91% on 724 stmts — **polluted**: 17 of 24
traced files are the editable `videos` dep (absent `[tool.coverage.run]` —
G-114 class, ~6th occurrence → AX-1). Own module: 231 stmts, 22 miss → 90%.
Consumer: `videos/infrastructure/cli.py:73-80` optional-imports it as
`AdvancedLinter` implementing the `Linter` port
(`application/ports/linter.py`); `VisualValidationStep` calls
`verify_visuals`/`verify_video` per rendered `.png`/`.mp4`.

## Surface inventory

| Module | SLOC | Public symbols | Entry |
|---|---|---|---|
| `linter_service.py` | 378 | `ContrastChecker.check_image`; `BlurDetector.check_image`; `ImageOverlapDetector.check_image`; `VideoMotionAnalyzer.analyze_video`; `LinterService.{verify_geometry,verify_visuals,verify_video}`; `LinterError`; `Box` alias. Privates: `_read_image`, `_frame_centroid`, `_detect_boxes`, `_collect_channel_boxes`, `_is_known_box`, `_intersection_area`, `_overlap_violation`, `_FrameStats`, `_collect_frame_stats`, `_longest_frozen_run`, `_is_brightness_sign_flip`, `_first_jump_distance` | ★ `Linter` port impl via videos cli |
| `__init__.py` | 1 | — (future-import only; no `__all__`) | — |

## Callgraph

```
verify_visuals(image_path, scene_id)                    [:437]
  ├─ ContrastChecker.check_image                        [:36]
  │   ├─ _read_image → cv2.imread → None→[]  ★P1        [:15-19,:39-41]
  │   ├─ GRAY → thresh>40 → findContours                [:43-50]
  │   │   per contour: w|h<5 skip (:57 UNCOV)
  │   │   fg_mask=roi>40; empty → skip (:66 UNCOV)
  │   │   bg_mask? p5-of-bg : [30,30,30] phantom        [:71-75]
  │   │   (:72-73 real-bg arm UNCOV — near-dead)  ★P2
  │   │   luminance on sRGB/255 (non-linearized) ★P4    [:77-94]
  │   │   ratio<4.5 → insufficient_text_contrast
  ├─ BlurDetector.check_image                           [:117]
  │   ├─ _read_image → None→[]  (:122 UNCOV)      ★P1
  │   └─ Laplacian var <100 → blurry_image
  ├─ ImageOverlapDetector.check_image                   [:192]
  │   ├─ _read_image → None→[]  (:197 UNCOV)      ★P1
  │   ├─ _detect_boxes → ×4 ch (B,G,R,GRAY):            [:143-149]
  │   │   _collect_channel_boxes: thresh>40→dilate      [:152-168]
  │   │   20²→contours→±3px dedup (_is_known_box);      same-channel merge ★P3
  │   │   w|h<5 skip (:164 UNCOV)
  │   └─ _overlap_violations O(n²)→_overlap_violation   [:200-234]
  │       area>10 & nest≤0.7 → visual_overlap
  └─ violations → LinterError (FIRST checker only) ★P8  [:438-448]

verify_video(video_path, scene_id)                      [:450]
  └─ VideoMotionAnalyzer.analyze_video                  [:315]
      ├─ VideoCapture; !isOpened→[] (:320 UNCOV)  ★P1
      │   release() NOT in finally — leak-on-raise ★P7
      ├─ _collect_frame_stats                           [:245]
      │   fps≤0→30 (:248 UNCOV); first-read fail→None (:252 UNCOV)
      │   per frame: mean, absdiff-mean, _frame_centroid
      │   (thresh>40→moments; m00≤0→None — dark frames) ★P9
      │   <2 brightnesses→None (:270 UNCOV — 1-frame → pass)
      ├─ stats None→[] (:324 UNCOV)               ★P1
      ├─ _check_frozen: _longest_frozen_run(diffs<0.05)/fps>15s [:274,:330]
      ├─ _check_flicker: Σextrema(|Δ|>10)/n>0.1         [:285,:349]
      └─ _check_stutter: first centroid-jump>80px       [:293,:376]
          (None-centroid pairs skipped; cut≡teleport) ★P9

verify_geometry(mobjects, scene_id) — 0 callers repo-wide [:413]  DEAD (G-140)
  └─ method-local import OverlapDetector (:418 ignore
      reportMissingTypeStubs on TYPED videos — editable py.typed
      invisible); per-call ctor; pairwise Any check_overlap
```

## Boundary table

| Boundary | Where | Faked as | Test |
|---|---|---|---|
| `cv2.imread` decode | `:16` ← all 3 image checkers | real PIL-generated pngs | test_{contrast,blur,overlap} — **no fail arm** |
| `cv2.VideoCapture` decode | `:318` ← `analyze_video` | real cv2-written mp4s | test_motion — **no fail arm** |
| `videos` `Linter` port | cli.py:74-80 optional import → step:26-30 | MagicMock ×4 + `sys.modules` patch (consumer side) | test_linter_service, videos test_cli |
| `videos.domain.quality.RuleViolation` | `:10` (shim path — G-147) | real pydantic VO | all tests |
| `OverlapDetector` (videos infra) | `:418-422` method-local, per-call ctor | — | **none — dead path (G-140)** |
| PIL image gen (dev-dep) | tests only | — | fixtures |
| Injected checkers | `:401-411` ctor DI | `MagicMock()` ×4 — not named fakes (ADR-0005) | test_linter_service |

## Dimension findings

| Dim | Suspect / measured | Evidence | Disposition |
|---|---|---|---|
| D1 | **Every decode/read failure → `[]` → lint passes** — 6 silent arms: `_read_image`→None→`[]` ×3 checkers (`:41,:122,:197`), `!cap.isOpened()`→`[]` (`:320`), `_collect_frame_stats`→None→`[]` (`:324` — also catches 1-frame videos via `:270`). Probe: missing .png, text-as-.png, missing .mp4, junk-bytes .mp4, 1-frame .mp4 → all `[]`; `verify_visuals`/`verify_video` on missing files → **no raise**. Only trace is an OpenCV C-level `WARN` on stderr. The gate green-lights corrupt/absent artifacts — G-104 evaluator-false-green class, but this IS the gate | probe (6/6 arms `[]`, 2/2 no-raise) | **G-164 S1** |
| D1 | **Phantom `[30,30,30]` background → false-PASS** — when a contour's ROI has no ≤40 px, `bg_mean=[30,30,30]` (`:71-75`). Probe: 200-on-100 uniform image → `[]` (passes; impl-math vs real bg = 1.89 <4.5 → should FAIL); 176-on-100 → reported 4.42 vs real-bg 1.67. Real-bg arm `:72-73` UNCOVERED — a contour bbox containing only bright pixels is the common case (dark bg never enters the ROI), so nearly every check runs against the phantom dark floor | probe + coverage | **G-165 S1** |
| D1 | **Same-channel overlap merge → missed violations** — `_detect_boxes` thresholds per channel: same-color overlapping elements fuse into ONE connected component → one box → no pair → `[]`. Probe: two overlapping white rects → `[]`; identical geometry in red-vs-green → 1 violation (the test suite covers only the channel-separated shape, test_overlap.py:31-33). Two colliding same-color text/elements are invisible to the rule | probe | **G-166 S1** |
| D1/D3 | **"Contrast ratio" is not WCAG luminance** — `:77-94` computes on raw sRGB/255, skipping linearization (`c/12.92 if ≤0.04045 else ((c+0.055)/1.055)^2.4`); `min_ratio=4.5` + rule name cite WCAG AA. Measured: gray46/white impl 4.56 vs true WCAG 13.58 (~3× stricter at the dark end → false-rejects what AA passes); 200/100 impl 1.89 vs 3.54; white/black and pure-hue pairs coincide (21.00/3.19) | computed table | **G-167 S3** |
| D3/D4 | **Port conformance statically invisible** — `LinterService` bases `[object]` (doesn't inherit `Linter`); pkg ships **no `py.typed`** → consumers must `ignore[reportMissingTypeStubs]` (cli.py:74) → `AdvancedLinter()` is Unknown → `Director(linter_service: Linter|None)` checks nothing; a signature drift on any of the 3 port methods propagates silently (G-41 unvalidated-contract class). Separately, `verify_geometry` does a method-local import + per-call `OverlapDetector()` (DI bypass vs ctor-injected siblings) on the dead G-140 path | `__bases__` probe + pyproject find | **G-168 S3** |
| D1 | **`verify_visuals` reports only the first failing checker** — elif-style loop `:438-448`: a frame failing contrast AND blur reports only "contrast issues" (probe: 45-on-30 flat patch → message names contrast only; blur/overlap silently dropped from the error) | probe | **G-169 S3** |
| D9/D10 | **Test bundle** — own cov 90% but all 6 decode-fail arms + `fps≤0` + first-read + `<2` + `verify_geometry` (:418-435) uncovered (22 lines); **mutation battery 9/14 SURVIVED**: `area<=10`→`<`, `nest>0.7`→`>=`, `flicker<=0.1`→`<`, `|Δ|<=10`→`<`, `frozen>=0.05`→`>`, `stutter>`→`>=`, `known-box<3`→`<=`, `w|h<5 or→and` ×2 — zero boundary assertions anywhere; killed: `ratio<`, `variance<`, `m00<=0`, `if violations`, `isOpened`; MagicMock ×4 vs ADR-0005 named fakes; `--cov` pollution 17/24 files = editable `videos` (G-114 class → AX-1); no `features/` — package's only surface is the `Linter` port behind `videos` cli (already AX-2-tagged via G-149) | cov + battery | **G-170 S4** |
| D1 | `cap.release()` not in `finally` (`:318-322`) — leaks the handle only if `_collect_frame_stats` raises; cv2 normalizes bad frames to `ret=False` → narrow window | reading | suspect, no row |
| D1 | `video_stutter_jump` fires on any ≥80px centroid jump — a hard scene cut ≡ teleport, indistinguishable by construction; all-dark frames give `m00=0`→centroid None→jump skipped (cuts between dark scenes invisible) | construction | suspect, no row |
| D1 | `element_{idx}` object_id = contour enumeration index — unstable identity, not an element reference (`:105`,`:231`) | reading | suspect, no row |
| D1 | `min_area > 0` guard dead — `w|h<5` filtered upstream → areas ≥25 (`:218`) | reading | suspect, no row |
| D1 | dilate-20² merges elements <~20px apart → near-touching distinct elements read as one box (deliberate kerning fix 8045ae5; tolerance) | reading | suspect, no row |
| D2 | per-call 1080p: contrast 93.5 ms, blur 159.3 ms, overlap 47.5 ms; motion 300-frame 200² 1122.8 ms — all linear-in-pixels/frames; `_overlap_violations` O(n²) on dedup-capped boxes; `_collect_frame_stats` 3 lists O(frames) | timeit | clean |
| D6 | no member-state accumulation (stateless checkers, ctor config only); `_FrameStats` ~23 MB worst at 3h×30fps — bounded per call, released | construction | clean |
| D7 | no shared mutable module/ClassVar state; `LinterService` DI'd deps are config-only → single-threaded by construction in the sequential pipeline | construction | clean |
| D8 | no request parsing / shell / yaml / pickle / secrets; `str(path)` to cv2 comes from the artifact store (author-side); no `eval`/`exec` | surface | clean |
| D4 | `verify_geometry` whole method dead (0 callers incl. tests — G-140 already names this impl for delete-or-wire; evidence: method-local import + per-call ctor + ignore on typed pkg) | grep | covered by G-140 |
| D5 | `from videos.domain.quality import` consumes the shim re-export (G-147 already registers the shim/canonical split) | grep | covered by G-147 |
| D1 | `LinterError(RuntimeError)` — lands in videos cli `except Exception` (:97); `check_image`/`analyze_video` return-type honesty OK (`list[RuleViolation]` always); `scene_id="unknown"` defaults fine (caller passes real ids) | reading | clean |

## Measurements

- **Coverage**: `pytest --cov` 14 tests; TOTAL 91% / 724 stmts — 24 files
  traced, **17 = editable `videos` dep** (domain/_base 67%, value_objects
  61-90%), 7 = own (2 src + 5 tests). Own `linter_service.py` 231 stmts / 22
  miss → 90%. Missing: `:18,:41` (imread-None ×2 sites), `:57,:66` (contrast
  skips), `:72-73` (real-bg arm), `:122,:164,:197`, `:248,:252,:270`,
  `:320,:324` (all video fail arms), `:418-435` (`verify_geometry` whole).
- **Silent-pass probe** (P1): `check_image`/`analyze_video` on missing /
  text-as-png / junk-mp4 / 1-frame → `[]` ×6 arms; `verify_visuals` +
  `verify_video` on absent paths → no `LinterError`. OpenCV emits
  `WARN findDecoder` on stderr; the library reports nothing.
- **Phantom-bg probe** (P2): PIL/cv2-generated 200² bg (100,100,100) +
  60×60 (200,200,200) element → `[]` (impl-math real-bg ratio 1.89);
  176-on-100 → violation `actual=4.42` (real-bg 1.67 — verdict same,
  number phantom-driven).
- **Merge probe** (P3): two overlapping (255,255,255) rects → `[]`;
  same geometry (0,255,0)+(255,0,0) → 1 `visual_overlap`.
- **WCAG table** (P4): white/black 21.00=21.00; gray46/white 4.56 vs 13.58;
  200/100 1.89 vs 3.54; 45/30 1.35 vs 1.21; yellow/blue 3.19=3.19.
- **Perf** (P6): 1080p per call — contrast 93.5 ms, blur 159.3 ms
  (Laplacian dominates), overlap 47.5 ms; `analyze_video` 300f@200²
  1122.8 ms. timeit n=10 (motion n=3).
- **Masking probe** (P8): 45-on-30 flat patch → `LinterError` names
  "contrast issues" only; blur/overlap violations absent from message.
- **Mutation battery** (shadow-PYTHONPATH copy, real suite): 14 flips →
  5 killed, 9 survived (all survivors relational-boundary: <=/<, >/>=
  families + `or→and` on both noise filters).
- **Contract** (P5): `LinterService.__bases__ == [object]`; `find
  py.typed` → only `libs/videos` ships one; consumer-side
  `ignore[reportMissingTypeStubs]` at cli.py:74 makes the injected object
  Unknown → `Director(linter_service: Linter|None)` unverifiable.

## Gaps promoted

| Gap ID | Severity | One-line |
|---|---|---|
| G-164 | S1 | every decode/read failure returns `[]` — missing/corrupt image/video, unopened capture, 1-frame video all lint-green |
| G-165 | S1 | contrast checker measures against phantom `[30,30,30]` bg when ROI has no ≤40 px → demonstrated false-PASS (200-on-100 → `[]` vs real 1.89) |
| G-166 | S1 | same-channel overlapping elements fuse at threshold → `visual_overlap` can't see same-color collisions (white-on-white probe → `[]`) |
| G-167 | S3 | "contrast ratio" skips sRGB linearization — impl scale ≠ the WCAG AA 4.5 it cites (~3× stricter dark-on-light) |
| G-168 | S3 | `LinterService` doesn't inherit `Linter` + pkg ships no `py.typed` → port conformance unchecked at the consumer boundary |
| G-169 | S3 | `verify_visuals` reports only the first failing checker — later violations dropped from the error |
| G-170 | S4 | 9/14 mutants survived (boundary flips); all decode-fail arms + `verify_geometry` uncovered; MagicMock ×4; cov pollution 17/24 editable `videos` (→ AX-1) |
