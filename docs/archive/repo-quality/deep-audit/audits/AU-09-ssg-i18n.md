# AU-09 — ssg-i18n audit (2026-10-01)

MA-4 step 4. Target: `libs/ssg-i18n` — 1135 LOC / 910 SLOC per radon raw
(`use_cases/document_translator.py` 439, `infrastructure/i18n_site_variant_provider.py`
280, `use_cases/terminology_mapper.py` 123, `yaml_translation_catalog_repository.py`
54, `plugin.py` 49, `catalog_first_text_translator.py` 28, `in_memory_text_translator.py`
18, VOs + ports 96, six re-export shims 48); 52 tests / ~1057 test LOC in two
trees (root `tests/unit/test_*.py` via shims + structured `tests/unit/{application,
domain,infrastructure}/`). Gates baseline: pyright strict 0 errors, 52 tests
pass in 6.3s — but `pytest --cov` TOTAL is 87% over 1906 stmts because bare
`--cov` traces editable `ssg`/plugin workspace deps (no `[tool.coverage.run]`;
own modules measure 89-96%). The plugin implements `ssg.site_variant_providers`:
one `SiteVariant` per configured locale, page bodies retranslated into
`.ssg/generated-i18n/<locale>/<collection>/` via a mistletoe parse →
sentence-level translate → re-render round-trip. Audit weight: the
marker/protect pipeline (TR{n}/MATHEXPR{n}), block/span dispatch coverage,
provider config seams (paths, modes, locales), EP factory, catalog load.

Reused verdicts (not re-audited): `SiteVariantProvider` port +
`_load_plugin` EP validation (`cli.py:194-201`, AF-29) → provider EP conforms;
`Site.extension_setting`/`selected_collections`/`navigation_for` (AU-04);
slug/containment validation in `site_config_repository` (AF-24/25) covers
`output_slug` + page `source` — **not** collection `name`
(`_required_string` only, `site_config_repository.py:82`) nor i18n extension
paths; `main()` catch tuple `(ValueError, TypeError, FileNotFoundError,
ImportError, RuntimeError)` at `cli.py:47-53`. mistletoe 1.5.1 under an
unbounded `>=1.3.0` specifier (uv.lock-pinned).

## Surface inventory

| Module | LOC | Public symbols | Entry |
|---|---|---|---|
| `use_cases/document_translator.py` | 439 | `DocumentTranslator` (`translate_file`, `translate_markdown_source`), `_CustomMarkdownRenderer`, module-level `block_token.remove_token` patch | injected `TextTranslator` |
| `infrastructure/i18n_site_variant_provider.py` | 280 | `I18nSiteVariantProvider` (`variants`★), `TranslationCatalogRepository`/`TextTranslatorFactory` Protocols | `ssg.site_variant_providers` EP `i18n` (pyproject:11-12) |
| `use_cases/terminology_mapper.py` | 123 | `TerminologyMapper` (`map_text`) | injected into `DocumentTranslator` (default instance) |
| `infrastructure/plugin.py` | 49 | `create_i18n_site_variant_provider`★, `EntryPointTextTranslatorFactory` (`create`) | EP factory; consumes `ssg_i18n.text_translators` EP group |
| `infrastructure/yaml_translation_catalog_repository.py` | 54 | `YamlTranslationCatalogRepository` (`load`) | ctor-injected into provider |
| `use_cases/catalog_first_text_translator.py` | 28 | `CatalogFirstTextTranslator` | built per locale in `variants` |
| `infrastructure/in_memory_text_translator.py` | 18 | `InMemoryTextTranslator` | plugin default + tests |
| `application/ports/text_translator.py` | 8 | `TextTranslator` `@runtime_checkable` Protocol | `ssg_i18n.text_translators` contract |
| `domain/value_objects/{locale,locale_set,translation_catalog}.py` | 64 | `Locale`, `LocaleSet`, `TranslationCatalog`, `EMPTY_TRANSLATION_CATALOG` | — |
| 6 re-export shims (`application/{document_translation,i18n_site_variant_provider,terminology_mapper,translation}.py`, `domain/{locale,translation_catalog}.py`) | 48 | same symbols | the public API `ssg-i18n-machine-translation` imports — keep |

## Callgraph

```
(ssg cli.py:194-201 load_site_variant_provider → _load_plugin)
create_i18n_site_variant_provider                          [plugin.py:18]
  └─ I18nSiteVariantProvider(InMemoryTextTranslator({}),
       YamlTranslationCatalogRepository(),
       EntryPointTextTranslatorFactory())                  [plugin.py:19-23]

variants(site, context)                                    [provider:55-62]
  ├─ _locale_set → LocaleSet (:7) rejects default∉locales;  [:223-234]
  │   dup tags pass (P11: "en,en" → 2 variants same out dir)
  └─ _variant_for × locales                                [:64]
      ├─ default → replace(site, locale, default_locale)   [:87-90]
      │   (original Page objects — tracker keys stable)
      └─ non-default → _localized_site                     [:80-109]
          ├─ _text_translator_for                          [:236-241]
          │   ├─ _translation_catalog:                     [:255-269]
          │   │   catalog_path = config.parent /           [:258-265]
          │   │   translations_path / f"{tag}.yaml"        (P9 read-escape)
          │   │   exists() && repo → load() else EMPTY
          │   └─ _fallback_text_translator                 [:243-253]
          │       mode ∉ {machine,manual_with_machine_fallback}
          │       → injected translator (P10 silent-manual)
          │       else factory.create() → EP load()()      [plugin:27-48]
          │       per-locale, unguarded raise (P12; AU-10 seam:
          │       model load × locales)
          ├─ _translate(title, description)                [:271-280]
          ├─ _localized_extensions                         [:111-125]
          │   └─ _ui_label_sources 12 EN strings overwrite
          │       author extensions.i18n.label_*           (P8)
          └─ _localized_collection × ALL collections       [:143-164]
              (collection_name filter never consulted — P13)
              └─ _localized_page × pages                   [:166-188]
                  ├─ .md/.ipynb → generated_root /         [:190-221]
                  │   relative source path → write via      (P9 write-escape;
                  │   translate_file (:95-110)              collection.name
                  │   ├─ .ipynb → json.loads →             unvalidated — P9b)
                  │   │   _translate_notebook [:118-132]   (P-nb-root AttributeError)
                  │   │   └─ _translate_notebook_source    [:146-154]
                  │   │       list → join; else str()      (P14 "None"/repr)
                  │   └─ .md → translate_markdown_source   [:156-189]
                  │       ├─ MATHEXPR{i} protect (math)    [:162-174] (P2)
                  │       ├─ mistletoe.Document            [:176]
                  │       │   (sets token._root_node, then clears)
                  │       ├─ _CustomMarkdownRenderer()     [:177, :37-74]
                  │       │   ctor → block_token.remove_token(Footnote)
                  │       │   → module patch guards 2nd+   [:22-34] (P15)
                  │       ├─ _translate_block(doc)         [:191-208]
                  │       │   recurse: Document/List/ListItem/Table/TableRow
                  │       │   translate: Paragraph/Heading/TableCell
                  │       │   ↳ Quote, SetextHeading ABSENT → children never
                  │       │     reached (P1 — silent skip, no else arm)
                  │       ├─ _translate_inline_children    [:232-253]
                  │       │   ├─ _translate_inline_nodes →
                  │       │   │   _render_token_in_sentence [:317-353]
                  │       │   │   RawText→text, Strong/Emphasis→
                  │       │   │   styled-protect, Link→label render
                  │       │   │   (NO translate call — P3a), InlineCode/
                  │       │   │   LineBreak→protect, else→renderer.render
                  │       │   │   raw syntax into text     (P3b: Image,
                  │       │   │   InlineHTML, AutoLink)
                  │       │   ├─ _protect_wikilinks (label → translate) [:413-429]
                  │       │   ├─ _protect_patterns ({{}}, {%%}, math,
                  │       │   │   URLs, MATHEXPR)          [:431-439]
                  │       │   ├─ _protect_glossary_terms   [:264-282]
                  │       │   │   └─ _get_glossary_terms   [:255-262]
                  │       │   │       isinstance(CatalogFirst) — port
                  │       │   │       pierce (P16); re.compile per term (P6)
                  │       │   ├─ text_translator.translate [:248]
                  │       │   ├─ _normalize_and_heal_markers [:284-301]
                  │       │   │   \b[Tt][Rr]\s*\d+\b rewrite (P4a);
                  │       │   │   prepend-on-drop (P4b dup)
                  │       │   ├─ _restore_and_postprocess  [:303-315]
                  │       │   │   all-markers→English fallback; map_text
                  │       │   │   (P7 locale-blind); str.replace restore (P2)
                  │       │   └─ span_token.tokenize_inner(finalized) [:253]
                  │       │       NO root → ref-link crash (P0)
                  │       ├─ marker restore reversed-order [:182-184,313-314]
                  │       └─ trailing-newline preserve     [:187-188]
                  └─ Page(slug, translated title, generated source_path)
                     [:184-188]
```

Dead-looking: none (vulture clean). Legacy-shape modules: the 6 shims are
re-export-only — canonical + shim paths both live; consumed by
ssg-i18n-machine-translation (`transformers_text_translator.py:5-6`,
`plugin.py:1`, `cli.py:5`) → intentional surface, not dead.

## Boundary table

| Boundary | Where | Faked as | Test |
|---|---|---|---|
| fs `read_text` page source | doc_translator:115,:121 | real `tmp_path` | all file tests |
| fs `mkdir`+`write_text` generated | :98-109 | real `tmp_path` | provider tests |
| fs catalog yaml read | yaml_repo:31 | real `tmp_path` + real yaml | catalog tests |
| `importlib.metadata.entry_points` | plugin:29 | — | **no plugin test file** |
| mistletoe internals (`_token_types`, `render_map`, token attrs) | :22-74,:197-199,:226-229 | real mistletoe | implicit via translate tests |
| `yaml.safe_load` | yaml_repo:31 | real | :36/:46 raise arms uncovered |
| `TextTranslator` port | ctor params | `InMemoryTextTranslator` + inline stubs | conformance test :13 |
| `TranslationCatalogRepository` Protocol | provider ctor | real yaml repo | provider tests |
| `TextTranslatorFactory` Protocol | provider ctor | `None` only | machine arm :250-253 uncovered |
| ssg domain objects | provider args | real `Site`/`BuildContext` | provider tests |
| global `token._root_node` | mistletoe span tokenize | — | the P0 crash seam |

## Dimension findings

| Dim | Suspect / measured | Evidence | Disposition |
|---|---|---|---|
| D1 | **Ref-style links crash re-tokenization — uncaught `AttributeError`**: `span_token.tokenize_inner(finalized)` (:253) runs with `token._root_node=None` (mistletoe `Document.__init__` sets it during parse, clears after — `block_token.py` Document init). Any `[x][r]`/`![x][r]`/`[x][]` in a translated paragraph → `match_link_label` → `root.footnotes` → `AttributeError` (traceback measured at mistletoe `core_tokens.py:306`). `AttributeError ∉ main()` catch tuple → raw traceback mid-build. Standard CommonMark, author-level input | P0 | **G-81 S1** |
| D1 | **`Quote`/`SetextHeading` (and any unlisted block with children) silently untranslated**: whitelist (:201,:207) recurses only `Document/List/ListItem/Table/TableRow`, translates `Paragraph/Heading/TableCell` — no `else`. Probe: `> quote` → 0 translate calls, output identical; `> - item` quoted list → 0 calls; `Sub\n---` setext → 0 calls. Whole subtrees silently stay English | P1 | **G-82 S1** |
| D2 | **No incremental or collection-scoped translation**: `variants()` runs on the full `site` before `selected_collections` filtering (`static_site_builder.py:75,117`) — counting fake: 68 translate calls for 2coll×3page×2-nondefault-locale site, **identical under `collection_name="coll0"`**; second `variants()` = +21 identical calls (every build re-does all pages; localized Pages are fresh objects each call — never `in affected_pages` → always re-render too). With a real MT backend this is the dominant build cost | P13 | **G-83 S2** |
| D2 | **Glossary protection is O(terms × sentence) with cache thrash**: `_protect_glossary_terms` `re.compile`+`pattern.sub` per glossary term per inline group (:267-281) — timeit 10/200/1000/2000 terms → 0.19/0.55/27.93/55.24 ms per sentence (superlinear past re's 512-entry cache). 50-sentence page @2000 terms ≈ +2.8 s | P6 | **G-84 S2** |
| D1 | **`TR{n}`/`MATHEXPR{n}` marker namespace collides with authored text**: source `"TR0 is a real acronym here. Use \`code\` now."` → both literal `TR0` and marker replaced → `` `code` is a real acronym here. ``; literal `MATHEXPR0` + `$x<y$` → `"The $x<y$ label and $x<y$ math."`. `str.replace` replaces every occurrence (:313-314,:182-184); `all(marker in translated)` (:309) is satisfied by coincidental literals. G-43 class | P2 | **G-85 S3** |
| D1 | **Marker heal corrupts text and duplicates content**: `\b[Tt][Rr]\s*\d+\b` (:290-294) rewrites legitimate `TR 9` → `TR9` in translator output; leading-marker drop → `marker + sep + normalized` prepend (:295-301) → `**bold** tail text` translates to `**texto de cauda** texto de cauda` — protected content duplicated in front of the full translation | P4 | **G-86 S3** |
| D1 | **Entity double-decode changes rendered output**: `&amp;copy;` → i18n md `©` → ssg renders `©` where author text should display literal `&copy;`; `&amp;` → `&` generally (mistletoe span decode → raw re-emit). G-57 class. Cosmetic reserialization also measured: `| a | b |` → `| a   | b   |`, `---`-delimited blocks gain a blank line | P5-ent | **G-87 S3** |
| D1 | **Notebook input shape unchecked**: top-level JSON list → `AttributeError: 'list' object has no attribute 'get'` (:122) — escapes `main()` catch → traceback (G-77 class); markdown cell with absent/`None` `source` → written back as literal `"None"` (:149-154 `str(source)`); dict source → `"{'a': 1}"` | P14 | **G-88 S3** |
| D1 | **Span dispatch gaps — labels untranslated, markup sent raw**: `Link` labels rendered via `_translate_inline_nodes` (no `translate` call — measured: label text absent from calls); `Image`/`InlineHTML`/`AutoLink` → `renderer.render` fallback (:353) embeds raw syntax in the text sent to the translator — `<em>inline</em>` and `![alt](img.png)` verbatim in call args; autolink URL protected mid-tag → `"Autolink <TR0 done."` | P3 | **G-89 S3** |
| D1 | **Author `extensions.i18n.label_*` overwritten on non-default variants**: `_localized_extensions` (:118-124) unconditionally sets all 12 `_ui_label_sources` keys → author config `label_language: "Idioma!"` → pt-BR variant carries `"Lingua"` (translated built-in) while the en variant keeps `"Idioma!"` | P8 | **G-90 S3** |
| D1 | **Unknown `translation_mode` silently behaves as manual**: `mode not in {"machine","manual_with_machine_fallback"}` else-branch (:247) swallows any string — `"machien"` → factory `create()` never called (0), title stays English, zero signal | P10 | **G-91 S3** |
| D1 | **Duplicate locale tags → duplicate variants**: `locales: "en,en"` → `LocaleSet` accepts → two identical `SiteVariant`s sharing `output_path` — double builds, double generated-file writes (G-33 dup class) | P11 | **G-92 S3** |
| D1/D5 | **Manual catalog is keyed on marker-bearing text**: catalog lookup runs AFTER protection — `"Use \`MLflow\` for tracking."` requires the key `"Use TR0 for tracking."` (the repo's own fixtures do this). Authoring against real source → silent miss (measured: entry written on raw source → generated md stays English); adding one inline span earlier in a sentence renumbers every key | P-cat | **G-93 S3** |
| D8 | **Unvalidated path components in generated/catalog joins**: `generated_path: "../escape-out"` → translated page written OUTSIDE `site/` (measured file at sibling of config dir); `translations_path: "../outside-catalogs"` → yaml loaded from outside the config tree (measured load); `collection.name` joined unvalidated as a path component (`_required_string` only — `_require_slug` covers `output_slug`+page slug, not `name`; `../x` traverses the locale dir). `locale.tag` safe (charset-validated). G-45 class — author-committed config boundary | P9 | **G-94 S3** |
| D1 | **`TerminologyMapper` applies pt-BR rules to every locale**: `map_text` (:11-123) runs on all non-empty translations regardless of `target_locale` — DE probe `"Batch Skript laeuft"` → `"Skript em Batch laeuft"`; `"O deploy do Batch Processor"` → `"O implantação do Processor em Batch"`. Rules also hardcode project-domain terms (`gasoduto`, `champion`) | P7 | **G-95 S3** |
| D4 | **`_get_glossary_terms` pierces the `TextTranslator` port**: `isinstance(self.text_translator, CatalogFirstTextTranslator)` (:255-262) — a port-conforming catalog-bearing wrapper gets `{}` → glossary protection silently skipped (measured: `.catalog`-exposing wrapper → `{}`). The function-local import is unjustified — `catalog_first_text_translator` imports only ports/domain; no cycle exists | P16 | **G-96 S3** |
| D1 | **Catalog YAML `str()` coercions** (:51-53): `{1: one, '1': uno}` → `{'1': 'uno'}` silent collision; `on:`/`true:` → `'True'`; list value → `"['x']"`; int value → `'42'`. G-06/G-16 class (both shipped elsewhere) | P-yaml | **G-97 S3** |
| D1 | **Translator EP loading unguarded**: `translator_entry_points[0].load()()` (plugin:35) — `load()` ImportError propagates raw without EP name/group; non-conforming object → `TypeError` naming the object repr, not the EP. G-41 class (ssg `_load_plugin` wraps EP name+group; this nested loader doesn't) | P12 | **G-98 S3** |
| D3/D1 | **mistletoe private-internals adaptation under unbounded `>=1.3.0`**: patches `block_token.remove_token`/`_token_types` (:22-34 — verified load-bearing: unpatched, 2nd `MarkdownRenderer()` raises `ValueError: list.remove(x)`), dispatches through `render_map` class-name strings, passes `max_line_length` kwarg into untyped internals, mutates token nodes via `setattr`+`noqa:B010`, reads `token.loose`. Declared spec floats (lock pins 1.5.1) — upstream drift breaks silently-adapting internals (sagemaker `patches.py` seed class). Dead `except ValueError` arm :30-31 (the `in` pre-check makes it unreachable) | P15 | **G-99 S3** |
| D6 | **`EMPTY_TRANSLATION_CATALOG` shares mutable dicts**: `EMPTY_TRANSLATION_CATALOG.translations["X"]="y"` pollutes the module-level VO for all users (measured); `TranslationCatalog` fields are plain dicts | P-eps | **G-100 S3** |
| D9 | **Coverage denominator polluted (3rd occurrence — AX-1 pattern)**: bare `--cov`, no `[tool.coverage.run]` — TOTAL 87% over 1906 stmts incl. editable `ssg`, `ssg-notebook-render`, `ssg-syntax-highlighting`; own modules 89-96%; floor 75 vs sibling 95. G-68/G-78 class | P-cov | **G-101 S3** |
| D9/D10 | **Assertion-weak + missing surfaces**: 5/10 mutants SURVIVED — M1 `translation_mode not in`→`in` (machine-factory arm :250-253 uncovered + untested), M2 heal-prepend drop (:301), M5 yaml non-dict guard→AttributeError-path (:45-46), M6 plugin `isinstance`→`True` (TypeError arm), M7 `in_list_loose is False`→`True` (tight-list arm :52); killed: Heading-whitelist, fullmatch→match, glossary `reverse`, `is_default` flip, wikilink `is None`. Uncovered: :124,:150,:247,:301,:348,:353,:364,:382-392 (`_translate_and_protect_link` body), provider :250-253, yaml :36,:46; **no `plugin.py` test file**; no `features/`/bdd → i18n variant surface → AX-2; tests split across two trees (root shim-import files + structured canonical files — different subsets, both live) | mutation run; cov | **G-102 S4** |
| D1 | leading-marker heal targets only the FIRST marker (`re.match ^` on original); mid-sentence drops → full English fallback — designed fallback, tested (:157) | reading | suspect, no row |
| D6 | `.ssg/generated-i18n/` orphans: deleted pages leave generated files (no cleanup code) — bounded by content churn, files are inputs not outputs | reading | suspect, no row |
| D7 | `block_token`/`span_token` module-globals (`_token_types`, `_root_node`) + import-time monkeypatch: single-threaded by construction — `variants()` runs in the builder's sequential for-loop (`static_site_builder.py:88`), watchdog handler synchronous | code path | clean |
| D3 | 4 file-level pyright disables + `type: ignore`/`noqa:B010` — documented at :1-7 (untyped mistletoe internals); honest per ADR-0004 | reading | clean |
| D4 | injected ports (`TextTranslator`, `TranslationCatalogRepository`, `TextTranslatorFactory`, `TerminologyMapper`) earn their place — real variance at each seam | reading | clean (pierce → G-96) |
| D5 | names specific; largest file 439 < 500; public surface = EP + shims | reading | clean |
| D8 | `yaml.safe_load` ✓; no subprocess/pickle/eval; `Locale` charset-validates the one path component that's user-shaped | reading | clean (joins → G-94) |
| D10 | one real end-to-end integration test (`test_i18n_static_site_generation`, `pytest.mark.integration`) composes builder+renderers+post-processor — strong seam coverage but not bdd-shape; AX-2 carries the surface matrix | reading | folded into G-102 |

## Measurements

- **P0 (ref-link crash)**: `translate_markdown_source("[ref link][r]\n\n[r]: /dest\n")`
  → `AttributeError: 'NoneType' object has no attribute 'footnotes'` —
  `tokenize_inner`(:253) → `find_core_tokens(string, token._root_node)` →
  `match_link_label` → `root.footnotes.get` at mistletoe `core_tokens.py:306`.
  `Document.__init__` sets/clears `token._root_node` around its own tokenize.
  `isinstance(AttributeError, main-catch-tuple)` False → traceback.
- **P1 (block skip)**: `"> quoted words here\n\nplain words here\n"` → calls
  `['plain words here']` only; `"> - a\n> - b"` → 0 calls; `"Sub\n---\n"`
  (SetextHeading) → 0 calls; `"Setext\n===\n"` → 0 calls.
- **P2 (marker collision)**: `"TR0 is a real acronym here. Use \`code\` now."`
  → `` `code` is a real acronym here. Use `code` now. `` (literal replaced);
  `"The MATHEXPR0 label and $x<y$ math."` → `"The $x<y$ label and $x<y$ math."`.
- **P3 (span dispatch)**: `"A [the link text](http://x) here."` → calls
  `['A TR0 here.']` — label never translated; `"See ![alt](img.png) here."` →
  calls contain raw `"See ![the alt text](img.png) here."`;
  `"before <em>inline</em> after"` → raw `<em>` in call arg;
  `"Autolink <http://example.com> done."` → english `"Autolink <TR0 done."` —
  URL protected mid-`<…>` leaving a dangling bracket.
- **P4 (heal)**: translator echoing `"Execute TR 9 e depois "+s` on
  `"Run \`x\` now."` → `"Execute TR9 e depois Run \`x\` now.\n"`; dropper
  translator on `"**bold** tail text"` → `"**texto de cauda sem marcador**
  texto de cauda sem marcador\n"` (duplicated via :301 prepend).
- **P5-ent (double-decode)**: `"The entity &amp;copy; is text."` → md `©` →
  ssg-rendered `©` (original renders literal `&copy;`); `&amp;` → `&`.
- **P6 (glossary timeit)**: 10-para-1-sentence input, n=20 warm:
  10→0.19 ms, 200→0.55, 1000→27.93, 2000→55.24 ms per
  `translate_markdown_source` call (~×100 for ×10 past cache).
- **P7 (locale-blind terms)**: `map_text("Batch Verarbeitung ist fertig")` →
  `"Verarbeitung em Batch ist fertig"`; end-to-end DE translate →
  `"Skript em Batch laeuft"`.
- **P8 (label overwrite)**: `extensions.i18n.label_language="Idioma!"` →
  en variant keeps `"Idioma!"`, pt-BR variant carries `"Lingua"`.
- **P9 (path escape)**: `generated_path:"../escape-out"` → file exists at
  `work/escape-out/pt-BR/coll0/page0.md` (sibling of `site/`); default
  `.ssg/generated-i18n` dir not created. `translations_path:"../outside-catalogs"`
  → `repo.loads` records `site/../outside-catalogs/pt-BR.yaml`.
- **P10 (mode typo)**: `translation_mode:"machien"` + recording factory →
  `creates==0`, pt-BR title `"Site Title"` (English), no error/log.
- **P11 (dup locales)**: `"en,en"` → 2 variants, both `output_path=out/`.
- **P12 (EP errors)**: EP `.load` raising `ImportError("cannot import name 'x'")`
  → propagates verbatim (no EP name/group); `load()`→`lambda: object()` →
  `TypeError` naming `<object object at …>` not `"bad-translator"`;
  2 EPs → `ValueError` names both EPs ✓.
- **P13 (volume)**: site 2 coll × 3 pages, locales `en,pt-BR,fr` → 68
  `translate` calls with `collection_name=None` **and** `="coll0"`;
  1 coll × 2 pages `en,pt-BR` → build1=21 calls, build2 adds +21.
- **P14 (notebook shape)**: `[1,2]` → `AttributeError`; md cell no `source` →
  written `"None"`; `source:{"a":1}` → `"{'a': 1}"`; `cells:"x"` → clean
  ValueError (named path) ✓; non-JSON → `JSONDecodeError` (ValueError ✓).
- **P15 (monkeypatch)**: restoring original `remove_token` → 1st
  `MarkdownRenderer()` OK, 2nd → `ValueError: list.remove(x): x not in list`
  (`markdown_renderer.py:112` removes `Footnote` per ctor) — patch is
  load-bearing on 1.5.1; `except ValueError` at :30-31 unreachable after the
  `in` guard.
- **P16 (port pierce)**: wrapper exposing `.catalog` but not CatalogFirst →
  `_get_glossary_terms()` returns `{}` vs `{'Deploy':'X'}` via CatalogFirst.
- **P-yaml (coercion)**: `{1:,'1':}` → `{'1':'uno'}`; `on:`/`true:` →
  `'True'` key; `glossary: {deploy: [x]}` → `"['x']"`; non-dict section →
  clean ValueError; non-dict root → clean ValueError.
- **P-cat (contract)**: catalog `{"Use \`MLflow\` for tracking.": "…"}` →
  generated md unchanged English; fixture keys carry `"Use TR0 for tracking."`.
- **P-cov**: `pytest --cov` 52 pass; TOTAL 87% (1906 stmts incl. editable
  ssg 60-96%, notebook-render 50-55%, highlighting 89-90%); own:
  document_translator 91% (miss 30-31,52,124,150,247,301,348,353,364,382-392),
  provider 96% (miss 250-253), yaml 89% (miss 36,46); floor 75.
- **Mutations** (ephemeral flips, reverted — `git status` clean): SURVIVED
  M1 mode `not in`→`in`, M2 heal-prepend drop, M5 yaml `isinstance`→`if False`,
  M6 plugin `isinstance`→`True`, M7 `in_list_loose is False`→`True`;
  KILLED M3 Heading-removal, M4 fullmatch→match, M8 glossary `reverse` drop,
  M9 `is_default` flip, M10 wikilink `is not None`→`is None`. 5/10 survived.
- **Perf baseline**: identity translate of a 10-paragraph page = 8.00 ms
  (mistletoe `Document` alone 1.32 ms) — reserialization ≈ 6.7 ms/page/build
  even with zero work.
- **Gates baseline**: pyright strict 0 errors; 52 tests in 6.26s; both EP
  groups live in the workspace env.

## Gaps promoted

| Gap ID | Severity | One-line |
|---|---|---|
| G-81 | S1 | `tokenize_inner` without root → `AttributeError` traceback on `[x][r]`/`![x][r]` links — escapes `main()` catch, aborts mid-build |
| G-82 | S1 | `Quote`/`SetextHeading`/unknown blocks-with-children silently skipped — quoted text + setext headings never translated |
| G-83 | S2 | every `build()` retranslates every page × every locale; `--collection` doesn't scope (68 calls either way); localized pages never `in affected_pages` |
| G-84 | S2 | `_protect_glossary_terms` recompiles+scans per term per sentence — 0.19→55.24 ms/sentence at 10→2000 terms |
| G-85 | S3 | `TR{n}`/`MATHEXPR{n}` markers collide with literal text — authored `TR0`/`MATHEXPR0` replaced by protected content (G-43 class: unguessable markers) |
| G-86 | S3 | marker heal: `\b[Tt][Rr]\s*\d+\b` corrupts `TR 9`; leading-drop prepend duplicates protected content in output |
| G-87 | S3 | entity double-decode: `&amp;copy;`→`©` (renders changed); reserialization reformats tables/`---` blocks (G-57 class) |
| G-88 | S3 | notebook shape unchecked: non-dict root → `AttributeError` escapes catch; absent/null/dict `source` → `"None"`/repr written |
| G-89 | S3 | `Link` labels never translated; `Image`/`InlineHTML`/`AutoLink` raw syntax embedded in text sent to the translator |
| G-90 | S3 | author `extensions.i18n.label_*` unconditionally overwritten by translated built-ins on non-default variants |
| G-91 | S3 | unknown `translation_mode` (e.g. `"machien"`) silently behaves as manual — zero signal |
| G-92 | S3 | duplicate locale tags (`"en,en"`) → duplicate variants sharing `output_path` |
| G-93 | S3 | catalog keys require positional `TR{n}` markers (`"Use TR0 for tracking."`) — unauthorable/shift-on-edit → silent misses |
| G-94 | S3 | `generated_path`/`translations_path`/`collection.name` joined unvalidated — measured `../` write+read escapes (G-45 class) |
| G-95 | S3 | `TerminologyMapper` applies pt-BR rules to all locales (`"Skript em Batch"` in DE output); rules hardcode project-domain terms |
| G-96 | S3 | `_get_glossary_terms` isinstance-sniffs `CatalogFirstTextTranslator` — port pierced, wrappers lose glossary silently; lazy import unneeded |
| G-97 | S3 | catalog yaml `str()` coercions: `{1:,'1':}` collision, `on:`→`'True'`, list→`"['x']"` (G-06/G-16 class) |
| G-98 | S3 | translator EP `load()()` unguarded — raw `ImportError`; TypeError names object not EP (G-41 class) |
| G-99 | S3 | mistletoe internals adapted (`remove_token` patch load-bearing-verified) under unbounded `>=1.3.0`; dead except arm :30-31 |
| G-100 | S3 | `EMPTY_TRANSLATION_CATALOG` exposes mutable shared dicts |
| G-101 | S3 | bare `--cov` + no `[tool.coverage.run]` — editable-dep pollution (87%/1906 vs own 89-96%); floor 75 (3rd instance → AX-1) |
| G-102 | S4 | 5/10 mutants survived; plugin.py + machine-factory arm + link-protect body + heal-prepend + yaml/nb raise arms uncovered; no bdd → AX-2; dual test trees |

## Notes for AU-10+

- `ssg-i18n-machine-translation` implements `ssg_i18n.text_translators` — its
  `create()` is invoked **once per locale per build** via
  `EntryPointTextTranslatorFactory` (provider:250-253): model-load cost sits
  on the per-locale path — AU-10 should measure it (D6 mandatory there per
  backlog).
- The `ssg_i18n.application.*`/`domain.*` shims are that package's import
  surface — changes to canonical paths must keep the shims.
- `EMPTY_TRANSLATION_CATALOG` mutation + `TextTranslator` port contract will
  be exercised by the transformers adapter — G-96/G-100 fixes likely touch
  the same files.
- AX-1 watch: `str()`-coercion at boundaries is now 4× (G-06, G-16, G-44/45,
  G-97); bare-`--cov` pollution is 3× (G-68, G-78, G-101); marker-collision is
  3× (G-43, G-73, G-85); uncaught-error-type escapes `main()` 3× (G-65, G-77,
  G-81/G-88).
