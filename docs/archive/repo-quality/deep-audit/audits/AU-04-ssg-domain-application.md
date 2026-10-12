# AU-04 — ssg domain + application audit (2026-09-29)

MA-3 step 1. Target: `libs/ssg/src/ssg/domain/**` + `src/ssg/application/**`
(978 LOC / 823 SLOC per radon raw; 80 blocks, avg complexity A 1.875, max B(6)
`Site.selected_collections`, MI all A). Domain = 4 frozen entities + 12 value
objects; application = `StaticSiteBuilder` (357 LOC, the compile pipeline) +
`StaticSitePreview` (41) + 10 Protocol ports. Gates green baseline: pyright
strict, 54 tests pass, coverage on `ssg` 88% (in-scope: entities 82–98%,
use cases 100%, dead-surface VOs 70–90% — detail in D9 row).

## Surface inventory

| Module | LOC | Public symbols | Entry |
|---|---|---|---|
| `application/use_cases/static_site_builder.py` | 357 | `StaticSiteBuilder.build`★ | `cli.build_site` (`build` + preview `on_change`) |
| `application/use_cases/site_preview.py` | 41 | `StaticSitePreview.preview`★ | `cli.preview_site` |
| `domain/entities/site.py` | 120 | `Site.{selected_collections,navigation_for,extension_setting,html_language}` | builder :218,:248,:251,:257; templates `base/page/index.html` |
| `domain/entities/content_collection.py` | 100 | `ContentCollection.{source_file,video_path,image_path,page_href,first_page,root_href,page_by_slug,previous_page,next_page}` | markdown renderer :142,:162,:195,:253; `site.py:89` |
| `domain/entities/{article,page}.py` | 13/12 | `Article.has_table_of_contents`, `Page.file_name` | templates, builder :188 |
| `domain/value_objects/` ×12 | ~160 | `ArticleHeading.depth_class`, `demote_top_level_headings`, `BuildContext`, `RenderedPage/Index`, `SiteNavigation/Section/Link`, `PagerLink`, `LanguageLink.aria_current`, `SiteVariant` | `demote_*` ← markdown_content_renderer.py:98; rest via ports/templates |
| `application/ports/` ×10 | ~110 | `SiteRepository`, `PageRenderer`, `ContentRenderer`, `MarkdownRenderer`, `SiteVariantProvider`, `ArticleOutlineBuilder`, `DependencyTracker`, `HtmlPostProcessor`, `SiteReloader`, `PreviewServer` | `MarkdownRenderer` consumed by `ssg-notebook-render` (AU-08 seam); `SiteVariantProvider` by `ssg-i18n` (AU-09) |

## Callgraph

```
cli.main ─ build_site ─ StaticSiteBuilder.build(config, output, collection, changed_paths)
  ─ changed_paths is None or config ∈ changed → tracker.clear(), affected=None      [:56-64]
    else affected = tracker.affected_pages(changed)   [EMPTY tracker → ∅ → skip-all]
  ─ site_repository.load(config) → Site                                               [:66]
  ─ site.selected_collections(collection_name) → tuple | ValueError                   [:67]
  ─ site_variant_provider.variants(site, ctx) → (SiteVariant,...)                     [:75]
  ─ per variant: _build_variant
      ─ output_path.mkdir; _write_assets (page_renderer.assets → write_text)  [:120,:202-206]
      ─ _write_index → site.navigation_for(None,None)   [ALL collections — G-29/G-30]
        → RenderedIndex → page_renderer.render_index → index.html write_text  [:223-226]
      ─ per collection: _build_collection → mkdir; per page:
          ─ page ∉ affected → log page_build_skipped, continue                       [:170]
          ─ _render_body → ContentRenderer.can_render/render → _process_rendered_html
            → HtmlPostProcessor.process chain                                         [:278-294]
          ─ _rendered_page → previous_page/next_page (O(n) scan each — G-36)
            → article_outline_builder.build → navigation_for(coll,page)               [:241-248]
            → _pager_link(extension_setting("i18n",label_*)) → _page_language_links
          ─ page_renderer.render_page → write_text(f"{slug}.html")                    [:187-189]
cli.main ─ preview_site ─ repository.load → StaticSitePreview.preview
  ─ site_reloader.watch(paths, rebuild_and_reload, interval, ignored_paths)   [:35-40]
      rebuild_and_reload = on_change(changed) → getattr(server,"trigger_reload")()   [G-31]
  ─ preview_server.serve(output_path, host, port)  [blocking]
```

Dead-looking surface flagged: `page_by_slug` (0 consumers), `aria_current` ×2
(0 consumers — templates use `link.current` directly), `html_language` alive via
`index.html:6`/`page.html:7`; `MarkdownRenderer` port alive via
`ssg-notebook-render` (`notebook_content_renderer.py:268`).

## Boundary table

| Boundary | Where | Faked as | Test |
|---|---|---|---|
| fs writes (`mkdir`, `write_text` pages/index/assets) | builder :120,:158,:188-189,:206,:224 | real `tmp_path` dirs | all use-case tests ✓ |
| fs reads (`page.source_path`, `repository.load`) | ports → infra | `SpySiteRepository`; `SiteConfigRepository` in integration | ✓ |
| `os.path.relpath` language links | builder :354-357 | — (pure) | `test_build_adds_relative_language_links…` asserts exact hrefs ✓ |
| `uuid4` correlation id | builder :72 | nondeterminism ok (log-only) | — |
| `logging.getLogger` | builder :25 | `StructuredLoggingConfigurator` (infra) | — |
| 10 ports (repo, renderers, tracker, reloader, server, provider, outline) | use-case ctors | named spies `SpySiteRepository`, `SpyContentRenderer`, `SpyPageRenderer`, `SpyArticleOutlineBuilder`, `SpyHtmlPostProcessor`, `SpySiteReloader`, `SpyPreviewServer`, `LocalizedSiteVariantProvider` | ✓ named-fake convention holds |
| threads | `rebuild_and_reload` runs on watchdog `Timer` thread (watchdog_site_reloader.py:45-47) | — | single-threaded-by-construction claim below |
| yaml/env/subprocess/pickle/network | none in scope | — | — |

## Dimension findings

| Dim | Suspect / measured | Evidence | Disposition |
|---|---|---|---|
| D1 | **Preview rebuild is a no-op**: `cli.build_site` constructs a fresh `InMemoryDependencyTracker` every call (`cli.py:85`); `preview_site.on_change` → `build_site(changed_paths)` → fresh tracker → `affected_pages()=∅` → `∅ is not None` → every page hits `page_build_skipped`. Probe: real `build_site` twice — edit `README.md` v1→v2, rebuild with `changed_paths={md}` → `overview.html` byte-identical, `CHANGED` absent; fresh tracker `affected_pages({md})` → `set()`. Contrast: persistent tracker → 2nd build renders (2 calls). Index+assets still rewritten — feature looks alive while pages never update | `static_site_builder.py:56-64,169-181` + `cli.py:85` + probe | **G-28 S1** |
| D1 | **`--collection` index nav lists ALL collections**: `_write_index` passes `site.navigation_for(None,None)` which iterates `self.collections` (`site.py:54-67`) while `RenderedIndex.collections=selected` — nav hrefs point into unbuilt trees. Probe: 2-collection site, `build(collection_name="coll_a")` → `coll-b` hrefs in index.html, `out/coll-b/` absent → dead links | `static_site_builder.py:215-218`, `site.py:54` | **G-29 S3** |
| D1 | **Any empty collection crashes every build**: index nav calls `root_href()`→`first_page()` (ValueError on empty) for every collection — even unselected. Probe: (ok, empty) site + `--collection coll_a` → `ValueError: Empty collection coll_b` aborts build | `content_collection.py:56-65` ← `site.py:89` | **G-30 S3** |
| D3 | **`trigger_reload` is off-protocol**: `PreviewServer` port declares only `serve` (`preview_server.py:5-7`); `site_preview.py:29-33` duck-types `getattr(...,"trigger_reload",None)` — a conforming adapter silently disables live reload. Probe: bare `serve`-only server → change event → no error, no reload | `site_preview.py:29-33` | **G-31 S3** |
| D1 | **`ignored_paths` path-base mixing → rebuild loop risk**: cli passes un-resolved `output_path` (`cli.py:116`); watchdog events inherit scheduled-path bases — config dir as-passed (may be relative), `source_root`s resolved absolute (`site_config_repository.py:187`). `_is_ignored` compares `Path ==`/`in .parents` without `.resolve()` (`watchdog_site_reloader.py:49-53`). Probe: ignored=`Path("site/build")` + abs event `/x/site/build/i.html` → False (not ignored) → writes under watched tree re-fire → every event loop rewrites index+assets (with G-28, that's all a rebuild does) | cli.py:116 + watchdog:49-53 (fix surface AU-05) | **G-32 S3** |
| D1 | **Duplicate page slugs silently overwrite**: `file_name()={slug}.html`; two `slug: dup` pages → second `write_text` wins. Probe: FIRST content absent from `dup.html`, SECOND present. Same class: duplicate collection `name`/`output_slug` collide in `selected_collections`/`mkdir` | `page.py:10-11`, `static_site_builder.py:188-189` | **G-33 S3** |
| D8 | **Slug path traversal**: `Page(slug="../escaped")` → `write_text` lands at `output_path/escaped.html` (outside collection dir; `../../` escapes output root). Author-committed config (G-04 precedent → S3 not S1); wikilink slug regex `([a-zA-Z0-9_-]+)` already safe (`markdown_content_renderer.py:243`) | `page.py:11`, probe: `out/escaped.html` exists | **G-34 S3** |
| D1 | **`demote_top_level_headings` unbalanced on non-canonical closers**: probe — `"<h1>a</h1 >"`→`"<h2>a</h1 >"`, `"<h1>a</H1>"`→`"<h2>a</H1>"` (open demoted, close untouched → malformed DOM). Reachable only via raw-HTML passthrough in md (markdown-it emits canonical `</h1>`) — bounded, legal input | `article_heading.py:19-21` | **G-35 S3** |
| D2 | **Nav+pager is O(n²)**: per page, `previous_page`/`next_page`/`_page_index` linear-scan (`content_collection.py:92-100`) and `navigation_for` rebuilds the section's full link tuple + `ContentCollection ==` tuple-eq (`site.py:76,62-67`). Measured n=100/500/2000 pages: **16.4 / 299.4 / 5234.1 ms** — 5×→18.3×, 4×→17.5× (slope ≈2). A 2000-page site pays +5.2 s of pure-Python nav per build | probes | **G-36 S2** |
| D4/D5 | **Dead public surface**: `page_by_slug` 0 consumers (uncovered :68-73); `aria_current` on `LanguageLink`/`NavigationLink` 0 consumers (templates use `link.current` — `navigation.html:20`, `header.html:21`; uncovered `language_link.py:11-14`, `navigation_link.py:14`) | grep + coverage | **G-37 S3** |
| D5 | **Duplicated lookup/error machinery in ContentCollection**: identical `expected_slugs` raise block ×3 (:51-53,:72-74,:97-99); `page_href` (`{slug}.html`) duplicates `Page.file_name()` | reading | **G-38 S3** |
| D9/D10 | **Test gaps at the wiring seam**: `site.py:40` (valid `--collection` select) uncovered — G-29 survived unseen; no test drives two `build_site` calls or `preview` on_change→build wiring — G-28 survived (unit test pre-populates a tracker the CLI never reuses, `test_static_site_builder.py:398-441`); `getattr`-returns-None branch untested; no `tests/bdd/` (repo convention exists: `athena-local`, `projects/*`); user surfaces = `build`, `preview`, `--collection` → tag AX-2 | coverage + reading | **G-39 S4** |
| D7 | Use-case objects per-build; tracker + spies confined to the calling thread; only cross-thread edge is `rebuild_and_reload` on watchdog's Timer thread → `_sse_queues` (infra). Entities frozen, VOs immutable → **single-threaded-by-construction** for this scope | cited entry points | clean |
| D6 | No unbounded stores in domain/app. Note for AU-05: a *persisted* tracker (post-G-28 fix) accumulates dead path keys across rebuilds — `clear()` only fires on config change | `in_memory_dependency_tracker.py:10` | report note |
| D1 | Variant-page staleness suspect **closed**: i18n-style providers rebuild `Page`s deterministically from the same loaded config and register their own deps through the shared tracker — probe: translated variant page DID re-render on source change. Residual for AU-09: variant deps key on *translated* source paths (`i18n_site_variant_provider.py:177-184`); original-source edits don't mark variant pages affected — convergence depends on the watcher seeing the translated file write | probe D | suspect closed |
| D3 | `Site.extensions: dict|None` mutable field in frozen entity (unhashable Site — never hashed, benign); `BuildContext` (domain VO) TYPE_CHECKING-imports `application.ports.DependencyTracker` — domain→application layering inversion; `extension_setting("i18n",…)` magic keys consumed by core + templates | `site.py:17`, `build_context.py:4-9`, builder :251,:256 | suspects only — design notes |
| D9 | Mutation spot-checks: `page_index == 0`→`!= 0` KILLED (entity+link tests); `next_index >= len`→`<` KILLED; `not in affected_pages`→`in` KILLED (incremental test); `../` prefix drop KILLED (nav href test); `</h1>`→`</h2>` replace drop KILLED (exact-string assert `test_html_article_outline_builder.py:13`) | 5 flips | assertions adequate on tested paths; gaps in G-39 |
| D4 | Ports earn their place: 2 reloader adapters, pluggable renderers/post-processors/providers via entry points, tracker is a real stateful seam. `PreviewServer` under-declares (→G-31); `MarkdownRenderer` port exists for the notebook plugin, not self-use — legit | reading | clean |

## Measurements

- **Probe A (G-28)**: `build_site` → edit `README.md` → `build_site(changed_paths={md})` → `overview.html` identical, `CHANGED` absent. Fresh tracker `affected_pages({md})` → `set()`. Persistent tracker → 2 render calls.
- **Probe B (G-29)**: `build(collection_name="coll_a")` → `"coll-b" in index.html` True, `out/coll-b/` absent.
- **Probe C (G-30)**: `(coll_a ok, coll_b pages:[])` + `--collection coll_a` → `ValueError: Empty collection coll_b: expected at least one page`.
- **Probe E (G-31)**: bare `serve`-only `PreviewServer` → change event → no `AttributeError`, no reload — silent.
- **Probe F (G-32)**: `_is_ignored(Path("/x/site/build/i.html"))` with `ignored=(Path("site/build"),)` → False; rel/rel → True.
- **Probe D (closed)**: persistent tracker + provider rebuilding `Page`s (translated titles) → both variants re-rendered on source change.
- **Probe G (G-33)**: two `slug: dup` pages → `dup.html` contains SECOND, not FIRST.
- **Probe I (G-34)**: `slug="../escaped"` → `out/escaped.html` exists (outside `out/c/`).
- **Probe demote (G-35)**: `"</h1 >"`, `"</H1>"` closers un-demoted; openers demoted → mismatched tags.
- **Probe J (G-36)**: `previous_page`+`next_page`+`navigation_for` per page, n=100/500/2000 → 16.4/299.4/5234.1 ms (≈O(n²)).
- **Coverage** (`--cov=ssg`): 88% total; in-scope: `content_collection.py` 82% (uncovered :35,:51-52,:60,:68-73 dead,:97-98), `site.py` 98% (:40), `language_link.py` 70%, `navigation_link.py` 90%, use cases 100%. 54 tests pass, 1 skipped (preview-server hangs under coverage), 1 deselected.
- **Mutations**: 5 flips in `content_collection`/`site`/`static_site_builder`/`article_heading` — all killed (4 observed failing, 1 by exact-equality assertion analysis).

## Gaps promoted

| Gap ID | Severity | One-line |
|---|---|---|
| G-28 | S1 | Preview rebuild no-op: fresh `InMemoryDependencyTracker` per `build_site` → all pages skipped |
| G-29 | S3 | `--collection` index nav lists all collections → dead links |
| G-30 | S3 | Any empty collection crashes the whole build via index nav `root_href` |
| G-31 | S3 | `trigger_reload` duck-typed off `PreviewServer` port → silent no-reload |
| G-32 | S3 | `ignored_paths` relative/absolute mixing → output writes re-trigger rebuilds |
| G-33 | S3 | Duplicate page slugs / collection names overwrite silently |
| G-34 | S3 | `slug="../x"` writes outside the collection dir (author-config traversal) |
| G-35 | S3 | `demote_top_level_headings` unbalanced on `</h1 >`/`</H1>` → malformed HTML |
| G-36 | S2 | Nav+pager O(n²): 5.2 s pure-Python nav at n=2000 pages |
| G-37 | S3 | Dead surface: `page_by_slug`, `aria_current` ×2 |
| G-38 | S3 | `ContentCollection` error machinery duplicated ×3; `page_href` duplicates `file_name` |
| G-39 | S4 | Wiring-seam tests absent (preview rebuild, `--collection` select, getattr-None); no bdd features → AX-2 |
