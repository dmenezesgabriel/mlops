# AU-05 — ssg infrastructure + CLI audit (2026-09-29)

MA-3 step 2. Target: `libs/ssg/src/ssg/infrastructure/**` — 1162 LOC / 959 SLOC
per radon raw; 89 blocks, avg complexity A 2.09, max B(7)
`PollingSiteReloader._signature`, MI all A. Hosts the `ssg.*` entry-point
loading contract every MA-4 plugin implements, the markdown render pipeline
(transclusion/wikilink/asset-copy), YAML config → `Site`, both reloader
adapters, the threaded preview server, and the CLI. Gates baseline: pyright
strict, 54 tests pass + 1 skipped (preview-server self-skips under coverage),
ssg coverage 88%; infra module coverage 29%–100% (detail in D9 row).
AU-04 contract verdicts reused: `page_href`/`source_file`/`video_path`/
`image_path` raise shapes verified there, not re-audited.

## Surface inventory

| Module | LOC | Public symbols | Entry |
|---|---|---|---|
| `cli.py` | 181 | `create_parser`, `main`★, `build_site`, `preview_site`, `load_content_renderers`★, `load_html_post_processors`★, `load_site_variant_provider`★, `validate_reload_interval` | `python -m ssg.infrastructure.cli` (root Makefile :98,:109; no console script) |
| `markdown_content_renderer.py` | 253 | `MarkdownContentRenderer.can_render`/`render`/`render_markdown`★ | `ContentRenderer` port + `MarkdownRenderer` port (AU-08 seam) |
| `site_config_repository.py` | 229 | `SiteConfigRepository.load`★ | `SiteRepository` port — `cli.build_site`/`preview_site` |
| `watchdog_site_reloader.py` | 87 | `WatchdogSiteReloader.watch`★, `DebouncedEventHandler` | `SiteReloader` port — `preview_site` |
| `polling_site_reloader.py` | 82 | `PollingSiteReloader.watch` | `SiteReloader` port — **0 non-test consumers** |
| `local_preview_server.py` | 68 | `LocalPreviewServer.serve`/`trigger_reload`/`shutdown`, `LiveReloadRequestHandler` | `PreviewServer` port — `preview_site` |
| `html_article_outline_builder.py` | 72 | `HtmlArticleOutlineBuilder.build` | `ArticleOutlineBuilder` port — `build_site` |
| `logging.py` | 43 | `StructuredLoggingConfigurator.configure`, `JsonLogFormatter.format` | `main()` |
| `frontend/media_components.py` | 63 | `FrontendFragmentRenderer.render_{source_panel,video_frame,image_frame}` | renderer `_include_source`/`_embed_*` |
| `in_memory_dependency_tracker.py` | 24 | `InMemoryDependencyTracker.register_dependency`/`affected_pages`/`clear` | `DependencyTracker` port — `build_site` |
| `jinja_page_renderer.py` | 22 | `JinjaPageRenderer.render_{page,index}`/`assets` | `PageRenderer` port — `build_site` |
| `frontend/site_assets.py` | 20 | `SITE_CSS`, `SITE_JS` (import-time `importlib.resources` reads) | `JinjaPageRenderer.assets` |
| `frontend/jinja_environment.py` | 9 | `create_frontend_environment` | `JinjaPageRenderer` ctor |
| `single_site_variant_provider.py` | 9 | `SingleSiteVariantProvider.variants` | `SiteVariantProvider` fallback — `build_site` |

## Callgraph

```
cli.main ─ StructuredLoggingConfigurator().configure (basicConfig force=True)
  ─ parse_args ─ "preview": validate_reload_interval (ValueError → propagates)
    ─ build_site(config, output, collection)          [ALWAYS runs pre-preview]
    ─ preview_site → SiteConfigRepository.load        [config loaded 2nd time]
      → site.selected_collections → watched_paths (frozen at start)
      → StaticSitePreview.preview → WatchdogSiteReloader.watch / server.serve
  ─ "build": build_site(config, output, collection)
      ├─ load_content_renderers: entry_points("ssg.renderers") → load()()  [raw]
      │     → (MarkdownContentRenderer, *plugins)   [first can_render wins]
      ├─ load_html_post_processors: entry_points("ssg.html_post_processors")
      │     → load()()  [order = entry_points order — unspecified]
      ├─ load_site_variant_provider: same; >1 → ValueError (→ propagates)
      ├─ lazy imports: HtmlArticleOutlineBuilder/InMemoryDependencyTracker/
      │     SingleSiteVariantProvider   [inconsistent w/ module-level imports]
      └─ StaticSiteBuilder.build → [AU-04 callgraph resumes]
            ↳ MarkdownContentRenderer.render → read_text(page.source_path)
              → render_markdown:
                  Environment(autoescape,StrictUndefined) + from_string  [per page]
                  → template.render(include_source, embed_video, embed_image)
                      include_source → collection.source_file (guarded) →
                        read_text → render_source_panel → _store_transclusion
                      embed_video/image → video_path/image_path → exists? →
                        mkdir + shutil.copy2 → render_*_frame → _store_transclusion
                  → _render_wikilinks (re.compile per call — re cache) → page_href
                  → MarkdownIt.render → demote_top_level_headings
                  → _replace_transclusions (2 × str.replace per marker)
SiteConfigRepository.load → yaml.safe_load → _required_mapping/_list/_string
  → _read_collection → _read_page (source_root/source — UNGUARDED vs
    source_file) → _read_videos/_read_images (identical bodies; str() coercions)
  → _read_extensions (str() key coercions) → _path_from_config (abs unnormalized)
DebouncedEventHandler.on_any_event [watchdog thread] → _is_ignored →
  Timer cancel+create → _flush → _execute_safely → on_change → build_site
PollingSiteReloader.watch [DEAD] → daemon Thread → _watch_forever:
  _signature (rglob + 2×stat per file per interval) → on_change(set())
LocalPreviewServer.serve → ThreadingHTTPServer.serve_forever [main thread]
  LiveReloadRequestHandler.do_GET [request thread] → /__live_reload__ →
    _sse_queues.append → queue.get(timeout=3600) → one-shot write → remove
  trigger_reload [reloader thread] → list(_sse_queues) snapshot → queue.put
  shutdown — test-only callers (test_local_preview_server, playwright smoke)
HtmlArticleOutlineBuilder.build → _HEADING_PATTERN.sub(add_heading_id)
  → _heading_label (tag strip) → _attribute_value (double-quote id only)
  → _unique_slug → _slugify
FrontendFragmentRenderer.render_* → own Environment(PackageLoader) [dup of
  create_frontend_environment] → get_template(fragment) → Markup(rendered)
JinjaPageRenderer.ctor → create_frontend_environment → get_template ×2
```

Dead-looking: `PollingSiteReloader` entire module (only `tests/` references);
`LocalPreviewServer.shutdown` production-unreached (tests + playwright only);
`suffix_languages`/`_language_class_for_source` reachable via `include_source`.

## Boundary table

| Boundary | Where | Faked as | Test |
|---|---|---|---|
| `entry_points()` ×3 groups | cli.py:122,135,149 | monkeypatch `cli.entry_points` + `FakeEntryPoint`/`FakeSiteVariantEntryPoint` | test_cli.py:120-157 — **renderers group untested** |
| `yaml.safe_load` | site_config_repository.py:27 | real tmp_path yaml | test_site_config_repository.py + integration ✓ |
| fs reads (`read_text` config/pages/includes, `importlib.resources`, PackageLoader) | repository:27; renderer:82,148; site_assets:5-14 | real tmp files | ✓ |
| fs writes (`mkdir`, `shutil.copy2`) | renderer:178-179,204-212 | real tmp dirs | ✓ image/video copy asserted |
| watchdog `Observer`/`Timer` threads | watchdog_site_reloader.py:45,81-87 | real FS events + `Event` waits | test_watchdog ×2 ✓ |
| `threading.Thread` daemon | polling_site_reloader.py:26-36 | real dirs; `_signature` privates | test_polling ×3 (dead surface) |
| `ThreadingHTTPServer` + request threads | local_preview_server.py:50-58 | real socket on port 0 | test_local_preview_server — **skipped under coverage** |
| `queue.Queue` SSE | local_preview_server.py:30-41,62-64 | real HTTP client | same skip caveat |
| logging root config | logging.py:40-43 | none needed (format pure) | — |
| `datetime.now(UTC)` | logging.py:10 | nondeterminism ok | — |
| Jinja `Environment` ×2 sites | media_components.py:10-14; renderer:110 | templates real | ✓ |
| subprocess/env/RNG/pickle | none in scope | — | — |

## Dimension findings

| Dim | Suspect / measured | Evidence | Disposition |
|---|---|---|---|
| D1 | **`main()` propagates raw tracebacks on every error path**: subprocess `build --config missing.yaml` → full `FileNotFoundError` traceback; `preview --reload-interval 0` → `ValueError` traceback (`cli.py:171-177`); `build --collection bogus` → `ValueError` traceback; missing `include_source` file → `FileNotFoundError`; `build_site`'s plugin loads → `ImportError` (probe P2a). G-17 precedent — scaffold `main()` shipped SystemExit-catch in AF-11 | cli.py:39-58 + probes | **G-40 S3** |
| D1 | **Entry-point load contract unvalidated**: `entry_point.load()()` (cli.py:123,136,150) — plugin `load()` raising propagates raw (ImportError probe); a zero-arg factory returning `object()` loads and is appended (`P2b`) — failure deferred to `renderer.can_render` `AttributeError` mid-build, decontextualized. Group/name never logged on failure | cli.py:120-162 | **G-41 S3** |
| D1 | **Author markdown executes as a Jinja template**: `{{ 7*7 }}` → `49` and `{{ [1,2,3]\|length }}` → `3` in rendered output (silent eval); `{{ undefined }}` → `UndefinedError` aborts the build; `{% set x=5 %}` executes/stripped (probes P3a-c). Any docs page containing literal `{{`/`{%` (e.g. templating docs) corrupts or crashes | markdown_content_renderer.py:110-132 | **G-42 S3** |
| D1 | **Transclusion marker collides with literal text**: source containing `SSG_TRANSCLUSION_0` + one real transclusion → literal occurrence replaced by panel HTML (`"SSG_TRANSCLUSION_0" in out` → False, 2× `source-panel` present). Self-generated marker comment says "never user input" but the *replace* scans rendered user HTML | markdown_content_renderer.py:223-236 | **G-43 S3** |
| D1 | **`str()` coercions on YAML keys/values** (G-06-class): `videos: {1: a.mp4, "1": b.mp4}` → silent collision (last wins); `extensions: {on: …}` YAML-1.1 key → `"True"`; `description: 42` → `'42'`; `output_slug: 123` → `'123'` — all probed. Sites: repository:18,54-56,100-103,122-125,140-143,158-163. mlops-shared shipped `_require_string_key` for exactly this | site_config_repository.py | **G-44 S3** |
| D1/D8 | **Page `source` traversal unguarded**: `source: ../secret.md` → `source_path` escapes `source_root`, `read_text` succeeds (probe). Asymmetric with `source_file()` which enforces containment (`content_collection.py:17-29`). Author-committed config — G-04/G-34 boundary → S3 | repository.py:79-81 | **G-45 S3** |
| D1 | **`_attribute_value` sees only double-quoted attrs**: `<h2 id='keep'>` → output `<h2 id="label" id='keep'>` — duplicate `id` attribute emitted (browser uses first → TOC href `#label` shadows author's `keep`). Bounded to raw-HTML passthrough | html_article_outline_builder.py:49-54,24-26 | **G-46 S3** |
| D4/D1 | **`PollingSiteReloader` is dead production code carrying a latent bug**: grep — 0 non-test consumers (`cli.preview_site` wires `WatchdogSiteReloader`); tests exercise `_signature`/`_rebuild_safely` privates only. And `watch` → `on_change(set())` (:24) → `affected_pages(∅)=∅` → no-op rebuild under the post-G-28 contract. `_signature` stats each file twice (:79). G-25 deletion precedent | module + probes | **G-47 S3** |
| D1 | **`watch()` silently skips nonexistent watched paths**: `if path.exists()` (:83) — probe: watch missing dir, create it, write file → 0 events. A mistyped `source_root` never reloads, no log | watchdog_site_reloader.py:82-84 | **G-48 S3** |
| D1 | **Embed basename collision**: videos `v1→va/demo.mp4` + `v2→vb/demo.mp4` → both write `assets/videos/demo.mp4` (`source_path.name` :176,:209); probe: file contains `BBB`, both anchors render `demo.mp4`. Same for images. G-33 overwrite class | markdown_content_renderer.py:171-184,204-217 | **G-49 S3** |
| D1 | **`JsonLogFormatter` drops messages on non-scalar context values**: `extra={"context":{"k": object()}}` → `json.dumps` `TypeError` → logging `handleError` prints "Logging error" and the record is lost. Keys are `str()`-ified (:28) but values aren't safe-encoded — G-03-class (the ssg copy reintroduced what mlops-shared's `_json_safe` fixed; ssg nests extras under `context` so the G-02 spoofing class doesn't apply) | logging.py:22-30 + probe | **G-50 S3** |
| D1 | **`_path_from_config` absolute branch unnormalized**: `Path("/a/b/../c")` returned as-is; relative branch `.resolve()`s (:187). G-05-class asymmetry | repository.py:180-187 | **G-51 S3** |
| D2 | **Per-page `Environment` + `from_string`**: `Environment(autoescape,StrictUndefined).from_string()` rebuilt every `render_markdown` (:110-111) — timeit: 0.155 ms env+compile vs 0.306 ms full `render` per page → **50.6% of per-page cost**; ~310 ms pure overhead at n=2000 pages. Constant-factor, not asymptotic — `_replace_transclusions` measured k=10/50/200 markers on ~55KB → 0.32/1.18/4.31 ms (linear-in-k, tiny constants: not a gap) | timeit probes | **G-52 S3** |
| D6 | **`InMemoryDependencyTracker` retains stale keys + Page objects**: 500 register cycles → 500 keys / 500 `Page`s pinned; nothing evicts except `clear()` on config change. Latent under today's fresh-per-call tracker — becomes a leak the moment G-28's fix persists it (the AU-04 report note). Measured growth → register now so the fix shape accounts for it | in_memory_dependency_tracker.py:10-21 + probe | **G-53 S3** |
| D9/D10 | **Infra test gaps**: `load_content_renderers` body uncovered (:121-130 — renderers group never probed); multi-provider raise :160, preview branch 47-58 + `preview_site` 98-104, `validate_reload_interval` accept-arm :173 uncovered (cli 73%); repository error-raise arms :88,:95,:110,:117,:134,:153,:199,:213,:227 uncovered (87%); **mutants survived**: M3 bare-`marker` replace drop (live behavior — inline `{{ include_source }}` mid-paragraph relies on it, verified) + M5 `_unique_slug` `==1`→`>=0` (duplicate-label dedup live behavior, verified); `local_preview_server` 29% **under coverage** — its test self-skips under tracing → module invisible to the `--cov-fail-under` gate; polling `watch`/`_watch_forever` uncovered (dead surface); `test_frontend_styles.py` tests `site_assets` (stale name — pre-refactor `styles.py` ghosts in `__pycache__`) | coverage + mutation runs | **G-54 S4** |
| D2 | Post-processor chain order = `entry_points()` order (unspecified); probe: registered `pygments`+`latex` commute on code+math input (identical bytes both orders) → **no demonstrated harm today** — stays a contract note | cli.py:133-143 + order probe | report note |
| D1 | `preview_site` computes `watched_paths` once from the first `load` (cli.py:98-103); a collection added to config mid-preview is never watched. Reading-verified (no reschedule path exists); timing probe not run — suspect, not measured | cli.py:98-117 | suspect — report only |
| D7 | SSE queue registry: 60 concurrent connect/disconnect + 1200 `trigger_reload` + mid-flood closes → 0 errors, queues drain 60→0. `list` append/remove GIL-atomic + `list()` snapshot iterate; queues unique per connection → `in`/`remove` TOCTOU benign. Debounce flood: 1000 events → 1 flush carrying all 1000 paths, 1000 canceled Timers | stress probes | clean (measured) |
| D8 | `SimpleHTTPRequestHandler(directory=…)` traversal probes `/../`, `/%2e%2e/`, `/..\` → all 404 (stdlib `translate_path`); `yaml.safe_load` ✓; `Markup`×4 carry `nosec` + invariant comments; wikilink charset `[a-zA-Z0-9_-]+` bounds `page_href` | probes + reading | clean |
| D3 | `cast(dict[object,object],…)` ×5 post-`isinstance(dict)` — honest (widens nothing); `cast(Callable…)` on optional plugin import — invariant commented (:30-39); `*args: Any`/`**kwargs: Any` on `LiveReloadRequestHandler.__init__` — stdlib ctor passthrough boundary, honest | reading | clean |
| D4 | `media_components` builds a second `Environment(PackageLoader)` duplicating `create_frontend_environment` (:10-14); `site_assets` does import-time fs IO (import→FileNotFoundError on broken install); `build_site` lazy imports vs module-level inconsistency; `SingleSiteVariantProvider`/`JinjaPageRenderer`/`StructuredLoggingConfigurator` earn their place | reading | design notes |
| D5 | `_read_videos`/`_read_images` identical bodies modulo key (:83-125, ~40 LOC dup); error messages uniformly include value + expected shape ✓ (repo rule) | reading | fold into G-44 fix surface |

## Measurements

- **CLI probes**: `build --config missing` → `FileNotFoundError` traceback (full trace, stderr); `preview --reload-interval 0` → `ValueError` traceback; `--collection bogus` → `ValueError`; missing `include_source` → `FileNotFoundError`; plugin `load()` raise → `ImportError`; non-conforming factory output → loads silently.
- **Jinja-over-markdown**: `{{ 7*7 }}` → `<p>Arithmetic: 49 and 3</p>`; `{{ undefined }}` → `UndefinedError`; `{% set %}` consumed.
- **Marker collision**: literal `SSG_TRANSCLUSION_0` in source → replaced by panel HTML (0 literal occurrences, 2 panels).
- **Coercion probes**: `description:42`→`'42'`; `on:`→`'True'`; `output_slug:123`→`'123'`; `{1:…,'1':…}` → single `'1'` key.
- **Traversal**: `source: ../secret.md` → escapes `source_root`, content read.
- **id quoting**: `<h2 id='keep'>` → `<h2 id="label" id='keep'>`.
- **Embed collision**: two `demo.mp4` dirs → one output file `b'BBB'`, two identical anchors.
- **Logging**: `context={"k":object()}` → `TypeError: Object of type object is not JSON serializable`.
- **D2**: env+`from_string` 0.155 ms/page vs `render` 0.306 ms/page (50.6%); `_replace_transclusions` k=10/50/200 → 0.32/1.18/4.31 ms @ ~55KB.
- **D6**: tracker 500 cycles → 500 keys, 500 retained `Page`s.
- **D7**: 60 SSE clients × 1200 triggers + closes → 0 errors, queues → 0; 1000 watchdog events → 1 flush, 1000 Timers.
- **D8**: 3 traversal probes → 404.
- **Order probe**: `pygments∘latex == latex∘pygments` byte-identical on math+code html.
- **Coverage** (`--cov` run): cli 73%, repository 87%, mcr 94%, watchdog 95%, polling 68%, outline 91%, site_assets 89%, logging 96%, lps 29% (self-skipping test), tracker/jinja/single-variant/frontend 100%.
- **Mutations**: 5 flips — M1 `<=1`→`<1` KILLED, M2 `_is_ignored`→False KILLED, M4 extension `isinstance` flip KILLED, M3 bare-marker-replace drop **SURVIVED** (live inline-transclusion path untested), M5 `count==1`→`>=0` **SURVIVED** (dup-heading dedup untested).
- **Probe hygiene note**: a same-byte-length mutation (`==`→`>=`) restored within the same second produced a stale `.pyc` that validated against restored source (timestamp+size check) — mutant leaked into a subsequent probe run. Mitigation used: purge `__pycache__` after mutation runs. Worth noting for future mutation workflows.

## Gaps promoted

| Gap ID | Severity | One-line |
|---|---|---|
| G-40 | S3 | `cli.main()` propagates raw tracebacks on all user-error paths (G-17 class) |
| G-41 | S3 | Entry-point loads unvalidated: crashes propagate raw; non-conforming plugin accepted |
| G-42 | S3 | Author markdown executes Jinja: `{{ expr }}` silently evaluates, `{{ name }}` crashes build |
| G-43 | S3 | `SSG_TRANSCLUSION_N` literal text collides with markers → content corruption |
| G-44 | S3 | `str()` coercions on YAML keys/values — G-06 class (collisions, `on:`→`True`, non-str fields) |
| G-45 | S3 | Page `source` path unguarded — escapes `source_root` (asymmetric with `source_file`) |
| G-46 | S3 | `_attribute_value` misses `id='x'` → emits duplicate `id` attribute |
| G-47 | S3 | `PollingSiteReloader` dead code + `on_change(set())` no-op rebuild + double-stat |
| G-48 | S3 | `watch()` silently ignores nonexistent `watched_paths` → collection never reloaded |
| G-49 | S3 | `embed_video`/`embed_image` basename collision overwrites same-named assets |
| G-50 | S3 | `JsonLogFormatter` non-scalar context value → TypeError → message dropped (G-03 class) |
| G-51 | S3 | `_path_from_config` absolute branch returned unnormalized (G-05 class) |
| G-52 | S3 | Per-page `Environment`+`from_string` = 50.6% of render cost (0.155 ms/page) |
| G-53 | S3 | Tracker retains stale path→Page keys across rebuilds (500/500 measured); lands post-G-28 |
| G-54 | S4 | Infra test gaps: uncovered loaders/error arms, 2 surviving mutants, coverage-invisible preview server |
