# AU-10 — ssg-i18n-machine-translation audit (2026-10-01)

MA-4 step 5 (last audit of the milestone). Target: `libs/ssg-i18n-machine-translation`
— 603 LOC / 503 SLOC per radon raw (`use_cases/machine_translation_evaluator.py` 327,
`infrastructure/transformers_text_translator.py` 110, `infrastructure/cli.py` 71,
`infrastructure/plugin.py` 8, `application/evaluator.py` shim 32, VOs 44,
`__init__`s 11); 18 tests / 468 test LOC split across two trees (root
`tests/unit/test_*.py` + structured `tests/unit/{application,domain}/` — the
AU-09 two-tree pattern). Gates baseline: pyright strict 0 errors, 18 tests pass
in ~2 s, radon cc clean, but `pytest --cov` TOTAL is 81% over 773 stmts — bare
`--cov` traces editable `ssg_i18n` (document_translator 56%, terminology_mapper
46%, locale_set 64%…) while own modules measure 93%; **`cli.py` and `plugin.py`
never appear in the report — zero coverage, invisible** (G-68/G-78/G-101 class,
4th occurrence). Backlog item's "in-memory translator" is stale wording —
`InMemoryTextTranslator` lives in ssg-i18n (audited AU-09); this package holds
the transformers translator, the evaluator use case, and the eval CLI.

Environment fact driving measurement choices: `transformers`/`torch`/
`sentencepiece` are **not installed** (optional `[transformers]` extra);
`sacrebleu` **is** installed (`[evaluation]` extra). The model boundary is
therefore measured via `sys.modules`-injected named fakes (the test suite's own
pattern) — call counts and option shapes are exact; resident-memory figures are
per-model-cite arguments, stated as such.

Reused verdicts (not re-audited): `TextTranslator` port is `@runtime_checkable`
(AU-09); ssg-side `_load_plugin` validates EP factory results (AF-29);
`EntryPointTextTranslatorFactory.create()` calls EP `load()()` **per locale per
`variants()` call** (AU-09 callgraph `i18n_site_variant_provider.py:236-253`)
→ this package's translator instances are never shared across locales or
rebuilds; `mistletoe>=1.3.0` unbounded with internals reliance (G-99 class);
`Locale` charset-validated upstream. Live `site/site.yaml` sets
`translation_mode: manual_with_machine_fallback` — this EP seam is live config;
root `Makefile:101` `evaluate-translation` recipe consumes the CLI.

## Surface inventory

| Module | LOC | Public symbols | Entry |
|---|---|---|---|
| `infrastructure/transformers_text_translator.py` | 110 | `TransformersTextTranslator` (`translate`), `TransformersModule` Protocol | `ssg_i18n.text_translators` EP `transformers` (pyproject:24-25) |
| `application/use_cases/machine_translation_evaluator.py` | 327 | `MachineTranslationEvaluator` (`evaluate`), `is_code_fence`, `is_empty_or_whitespace`, `is_math_block`, `is_horizontal_rule`, `clean_line_for_comparison`, `extract_text_nodes`, `render_node`, `evaluate_node_pair` | `evaluate` ← cli `main()`; helpers re-exported via shim |
| `infrastructure/cli.py` | 71 | `parse_arguments`, `print_report_summary`, `print_failures_and_logs`, `main`★ | console script `ssg-i18n-evaluate` (pyproject:22) |
| `infrastructure/plugin.py` | 8 | `create_transformers_text_translator`★ | EP factory, zero-arg |
| `application/evaluator.py` | 32 | re-export shim (`__all__` 11 names) | the import path `cli.py:6` + `test_evaluator.py` use |
| `domain/value_objects/line_result.py` | 14 | `LineResult` (frozen) | — |
| `domain/value_objects/translation_evaluation_report.py` | 30 | `TranslationEvaluationReport` (frozen) | — |

## Callgraph

```
(ssg_i18n provider _fallback_text_translator — machine/manual_with_machine_fallback
  → EntryPointTextTranslatorFactory.create → EP load()() — per locale per variants())
create_transformers_text_translator                     [plugin.py:7]
  └─ TransformersTextTranslator()                       [:8]
       model_name="Helsinki-NLP/opus-mt-tc-big-en-pt" fixed — no locale arg

translate(source_text, target_locale)                   [translator:21]
  ├─ _pipeline()                                        [:66]
  │   ├─ cached? return it                              [:67-70]
  │   ├─ import_module("transformers")                  [:72]
  │   │   ↳ ModuleNotFoundError propagates BARE when extra absent (P-noextra)
  │   ├─ isinstance(_, TransformersModule) else         [:73-76]
  │   │   RuntimeError (uncovered :74)
  │   └─ .pipeline("translation", model=model_name)     [:78-80]
  │       ↳ per-INSTANCE — N instances = N loads (P2)
  ├─ generation_options: max(16, min(128, words*4))     [:23-26]
  │   ↳ 128 cap binds >32 words (P4)
  ├─ "nllb" in model_name → src_lang eng_Latn +         [:27-31]
  │   tgt_lang _flores_lang_code(locale)                [:45-64]
  │   ↳ NON-nllb: target_locale NEVER read (P1);
  │     unmapped tag → raw "nl" as FLORES code (P5)
  ├─ pipeline(text, **opts) → result                    [:33-36]
  ├─ _translation_text: list + [0].translation_text     [:83-102]
  │   ↳ RuntimeError ×3 arms (uncovered :87,:99)
  └─ _looks_degenerate → return SOURCE on repetition    [:104-110]
      (<8 words gate; unique-ratio <0.35)

ssg-i18n-evaluate main()                                [cli.py:52]
  ├─ parse_arguments (Path/number types; locale raw)    [:12-28]
  ├─ MachineTranslationEvaluator(thresholds…)           [:54-59]
  │   └─ ctor translator=None → function-local import   [evaluator:122-127]
  │       → TransformersTextTranslator() (deferred import
  │         buys nothing — module is import-light)
  ├─ evaluate(src_dir, trans_dir, catalog, locale)      [evaluator:251]
  │   ├─ _find_file_pairs: rglob *.md × trans.exists()  [:134-143]
  │   │   ↳ missing translated file → dropped SILENTLY (P3a);
  │   │     missing source dir → 0 pairs → PASSED (P3b)
  │   ├─ _get_matched_nodes: Document(src)+Document(tr) [:145-159]
  │   │   extract_text_nodes — class-name dispatch,     [:47-67]
  │   │   Quote/SetextHeading/Jinja-para → [] (P11);
  │   │   count mismatch → LOG ONLY, zip(strict=False)  [:152-159]
  │   │   truncates → pass unaffected (P3c)
  │   ├─ _evaluate_node_list × files                    [:161-180]
  │   │   MarkdownRenderer() per file; render_node per  [:168,:70-78]
  │   │   node (Document([]) wrapper, type-ignore);     [:76-77]
  │   │   evaluate_node_pair → fallback/wiki/table      [:81-103]
  │   └─ catalog_path exists? _calculate_bleu_score     [:272-274]
  │       ↳ missing → bleu=None SILENT (P6); non-dict   [:217-218]
  │         yaml → AttributeError (P7)
  │       ├─ _get_bleu_sentences >5 words minus          [:203-210]
  │       │   hardcoded "Start with"/"The collector" (P9)
  │       └─ _gather_bleu_data: DocumentTranslator(      [:235-249]
  │           self._translator).translate_markdown_source
  │           per catalog key → corpus_bleu (pyright ignore :233)
  ├─ print_report_summary                               [cli.py:66]
  └─ failures → print_failures_and_logs + exit 1        [:67-71]
      ↳ logs printed ONLY on failure — mismatch invisible on pass (P3c);
        NO catch anywhere — every raise = traceback (P-main)
```

Dead-looking: `is_code_fence`, `is_empty_or_whitespace`, `is_math_block`,
`is_horizontal_rule` — zero call sites repo-wide (grep-verified), bodies
uncovered (:23,:27,:31-32,:38); reachable only through the `evaluator.py`
re-export. Legacy line-based evaluator leftovers.

## Boundary table

| Boundary | Where | Faked as | Test |
|---|---|---|---|
| `importlib.import_module("transformers")` → HF hub download + model memory | translator:72,78 | `FakeTransformersModule` injected into `sys.modules` (finally-restored) | test_transformers…:38-64 |
| HF pipeline callable | translator:19,33 | `FakeTranslationPipeline` / `Repeating…` / `CaptureOptions…` — via `_translation_pipeline` private poke | :70,:96 |
| fs `rglob`/`read_text` src+trans dirs | evaluator:138-149 | real `tmp_path` | all eval tests |
| `yaml.safe_load` catalog | evaluator:217 | real tmp yaml | BLEU test :156-194 |
| `sacrebleu.corpus_bleu` | evaluator:233 | real (installed) | BLEU high/low tests |
| mistletoe internals (`Document.children` set, `span_to_lines`, class-name dispatch) | evaluator:47-78 | real mistletoe | implicit via eval tests |
| EP `load()()` (`ssg_i18n.text_translators`) | plugin.py:7 | — | **no plugin test file** |
| `sys.argv` / process exit | cli.py:28,69-71 | — | **no cli test file** |
| `sys.modules` mutation | tests | n/a | suite-level global poke |

## Dimension findings

| Dim | Suspect / measured | Evidence | Disposition |
|---|---|---|---|
| D1 | **Evaluator reports PASSED on incomplete/absent input — silent false-pass on the tool's core promise**: (a) translated file missing → pair silently dropped (`trans_file.exists()` :141, not even a log): `passed=True, total=1, logs=[]`; (b) `--source-dir` nonexistent → `rglob` empty → `total=0` → `passed=True` → `Evaluation PASSED!` rc=0; (c) node-count divergence → `zip(strict=False)` truncates, message goes to `logs` only and `logs` print only under `if not report.passed` (cli.py:67-68) → `passed=True` with the warning unreachable in output. `test_evaluator_handles_node_count_mismatches_gracefully` pins `passed is True` on a divergent pair — the fix breaks a pinning test | P3a/P3b/P3c + live shape | **G-104 S1** |
| D6 | **Model loaded per translator instance; provider multiplies by locale × rebuild**: measured 2 instances/3 translates → 2 `pipeline()` calls, same model; no sharing seam (`_translation_pipeline` instance attr only). AU-09 evidence: `factory.create()` per non-default locale per `variants()` → N-1 co-resident model copies per build + a fresh load on every preview rebuild; each real pipeline holds a full seq2seq model (~1-2 GB class: opus-mt-tc-big / nllb-600M). Proxy-measured (transformers absent) — call multiplicity is exact, footprint is per-model | P2 + AU-09 :236-253 | **G-105 S2** |
| D1 | **`target_locale` ignored for non-NLLB models — silent wrong-language**: `translate("Hello world", Locale("fr")/"de")` → pipeline opts carry no `src_lang`/`tgt_lang`; model fixed `Helsinki-NLP/opus-mt-tc-big-en-pt` (pt output for any target). `src_lang`/`tgt_lang` set only when `"nllb" in model_name` (:27). EP factory takes no per-locale model arg — no config path exists to correct it. Bounded today: live site is `en,pt-BR` where the default model happens to be right; any added locale publishes pt content under that locale's URLs (G-95 locale-blind class, same reachability profile) | P1 | **G-103 S3** |
| D1 | **`max_new_tokens` cap silently bounds long sentences**: 50-word input → `max_new_tokens=128` while the 4×words budget wants 200 — HF `generate` clips at the cap without EOS → fluent-but-partial translations pass `_looks_degenerate` (unique-word ratio unaffected by truncation) | P4 | **G-106 S3** |
| D1 | **Unmapped locale → raw tag passed as FLORES code**: `Locale("nl")` on the nllb model → `tgt_lang="nl"` (valid code is `nld_Latn`) — `:64` returns `locale.tag` verbatim; model errors or mistranslates silently | P5 | **G-107 S3** |
| D1 | **Missing `transformers` extra → bare `ModuleNotFoundError`**: the `RuntimeError` guard (:73-76) covers present-but-nonconforming modules only; a missing module propagates `No module named 'transformers'` — doesn't name the `[transformers]` extra remediation. Live-measured: root `make evaluate-translation` recipe crashes today on the `--catalog-path` BLEU arm with a full traceback through `evaluate` → `translate` → `_pipeline` | live recipe run | **G-108 S3** |
| D1 | **`ssg-i18n-evaluate main()` catches nothing → traceback on every error path**: measured ModuleNotFoundError (live recipe), `ValueError` on `--locale bogus!` (`Locale` `__post_init__` rejects non-BCP-47), `AttributeError: 'list' object has no attribute 'get'` on a list-root catalog yaml (:218). G-17/G-40/G-88 class | 3 measured probes | **G-109 S3** |
| D1/D8 | **Catalog seams silent/unvalidated**: `--catalog-path` typo → `.exists()` guard (:273) → `bleu=None`, zero log (a requested check silently skipped — G-48 class); list-root yaml → `AttributeError`; dict yaml missing `translations` → `{}` → zero sentences → `bleu=0.0` → threshold failure naming BLEU, not the empty catalog | P6/P7 | **G-110 S3** |
| D1/D5 | **`_get_bleu_sentences` hardcodes content-specific excludes**: `not key.startswith("Start with")` / `"The collector"` (:208-209) — measured: catalog of 4 keys keeps only the ordinary sentence. Project-corpus filters baked into generic machinery (G-95 domain-leakage class) | P9 | **G-111 S3** |
| D1 | **`extract_text_nodes` evaluation blind spots**: `> quote` → 0 nodes; `> - a\n> - b` → 0; setext `H\n---` → 0; Jinja-bearing paragraph → 0 (:60-66 `has_jinja` whole-node drop). Post-AF-37 the translator DOES translate Quote/SetextHeading — the evaluator can never see their fallback/corruption (eval-side mirror of the G-82 dispatch defect); Jinja paragraphs escape checking entirely | P11 | **G-112 S3** |
| D4/D5 | **Four dead line-predicate helpers**: `is_code_fence`/`is_empty_or_whitespace`/`is_math_block`/`is_horizontal_rule` (:22-38) — zero call sites repo-wide (grep-verified), uncovered bodies; alive only via the `evaluator.py` `__all__` re-export (legacy line-based evaluator surface). G-25/G-47 deletion precedent | grep + cov | **G-113 S3** |
| D9 | **Coverage denominator polluted — 4th occurrence → AX-1**: bare `--cov`, no `[tool.coverage.run]` — TOTAL 81% over 773 stmts incl. editable `ssg_i18n` (document_translator 56%, terminology_mapper 46%, locale_set 64%, catalog_first 69%); own modules 93%; floor 75 vs sibling 95. Same shape as G-68/G-78/G-101 | cov run | **G-114 S3** |
| D3 | **Two ignore-comments carry no invariant note**: `# type: ignore[list-item]` (:77 — `Document.children` assignment on mistletoe internals, G-99 class) and `# pyright: ignore[reportUnknownMemberType]` (:233 — untyped sacrebleu). `cast(dict[str, Any], first_result)` (:94) is isinstance-guarded — honest; `Callable[..., object]`/`dict[str, object]` honest boundary shapes | reading | **G-115 S3** |
| D9/D10 | **Assertion-weak + invisible surfaces**: 7/9 mutants SURVIVED — M1 `min(128)` cap drop, M2 `trans_file.exists()` guard drop, M3 `bleu <`→`<=`, M5 `Start-with` exclude drop, M6 `unique_word_ratio <`→`<=`, M7 `len>3`→`>30`, M8 `catalog_path.exists()` drop; killed: `strict=False`→`True` (mismatch test), `"nllb" in`→`not in` (flores test). `cli.py`+`plugin.py` zero coverage and absent from the cov report (G-54-class invisibility); translator error arms :64,:74,:87,:99 + evaluator :23,:27,:31-32,:38,:53,:58,:66,:72-75,:232 uncovered; no `features/` → `ssg-i18n-evaluate` + EP surface → AX-2; tests split across two trees (G-102 class); private `_translation_pipeline` poked — no injection seam | mutation run + cov | **G-116 S4** |
| D1 | `translate` degenerate-guard returns **source** on repetition — feeds the evaluator's fallback metric by design; threshold `<0.35`/`<8` constants arbitrary but harmlessly conservative | reading | suspect, no row |
| D2 | BLEU loop is per-catalog-key `translate_markdown_source` (full mistletoe parse+protect+render per sentence): measured 10/50/200 keys → 6/12/50 ms with `InMemoryTextTranslator` — linear, ~0.25 ms/key; real cost is the MT model itself, inherent to evaluating MT | P12 | suspect, no row |
| D7 | `_pipeline()` lazy-init TOCTOU — worst case double model load, no corruption; ssg build/CLI paths are serial (single-threaded by construction: one `variants()` pass, one CLI invocation) | reading | suspect, no row |
| D4 | ctor function-local import of `infrastructure.transformers_text_translator` (:123-125) buys nothing — that module top-imports only ssg_i18n+importlib; mild layering smell, no contract forbids it (package has forbidden-import contracts only) | reading | suspect, no row |
| D6 | `logs` list grows one string per violation — bounded by node count per run | reading | suspect, no row |
| D3 | `TranslationEvaluationReport` frozen dataclass holds mutable `list[str]` fields — shallow freeze, bounded (report built once, returned) | reading | suspect, no row |

## Measurements

- **Coverage**: `pytest --cov` TOTAL 81% over 773 stmts; own modules
  `machine_translation_evaluator` 93% (missing :23,:27,:31-32,:38,:53,:58,:66,:72-75,:232),
  `transformers_text_translator` 93% (:64,:74,:87,:99); `cli.py`/`plugin.py`
  never appear in the report (0%, invisible); editable `ssg_i18n` traced into the
  denominator (document_translator 56% etc.).
- **P1 locale-ignore**: `CaptureOptionsFakeTranslationPipeline` — `translate`
  for `pt-BR`, `fr`, `de` → one `pipeline("translation",
  "Helsinki-NLP/opus-mt-tc-big-en-pt")`, per-call opts `{'max_new_tokens': 16,
  'no_repeat_ngram_size': 3}` — no locale key present.
- **P2 per-instance load**: 2 instances / 3 `translate` calls → `pipeline()`
  invocations = 2, both `model="Helsinki-NLP/opus-mt-tc-big-en-pt"`.
- **P4 token cap**: 50-word input → `max_new_tokens=128` (budget would allow
  200; cap binds for >32-word inputs).
- **P5 flores fallback**: `Locale("nl")` on `facebook/nllb-200-distilled-600M`
  → `tgt_lang="nl"` (raw tag, invalid FLORES code).
- **P3a missing trans file**: src 2 files / trans 1 → `passed=True, total=1,
  logs=[]`.
- **P3b missing src dir**: `rglob` on nonexistent dir → `passed=True, total=0`.
- **P3c structure mismatch**: 2 src nodes vs 1 trans node → `passed=True`,
  `failures=[]`, mismatch string in `logs` (prints only on failure).
- **P6 missing catalog**: `catalog_path.exists()` guard → `bleu=None`, no log.
- **P7 malformed catalog**: list-root yaml → `AttributeError: 'list' object has
  no attribute 'get'` at evaluator:218.
- **P-live**: `uv run ssg-i18n-evaluate --source-dir
  projects/nyc_taxi_demand_forecasting/docs --translated-dir
  site/.ssg/generated-i18n/pt-BR/… --catalog-path site/i18n/pt-BR.yaml` (the
  root `evaluate-translation` recipe, live dirs) → `ModuleNotFoundError: No
  module named 'transformers'` — full traceback, rc=1.
- **P-locale**: `--locale bogus!` → `ValueError: Invalid locale bogus!…`
  traceback, rc=1.
- **P9 bleu excludes**: 4-key catalog → `_get_bleu_sentences` keeps only the
  ordinary key; `Start with …`/`The collector …`/short keys dropped.
- **P11 extract blind spots**: `extract_text_nodes(Document(…))` → 0 nodes for
  quote, quote-list, setext heading, Jinja-bearing paragraph; 1 each for
  heading/plain paragraph.
- **P12 bleu scaling**: catalog 10/50/200 keys → `_calculate_bleu_score`
  0.006/0.012/0.050 s with `InMemoryTextTranslator` — linear per key.
- **Mutation run** (manual flips, suite = 18 tests): survived M1 min(128) drop,
  M2 `trans_file.exists()`→True, M3 `bleu <`→`<=`, M5 `"Start with"` exclude
  drop, M6 `unique_word_ratio <`→`<=`, M7 `len>3`→`>30`, M8
  `catalog_path.exists()` drop; killed M4 `strict=False`→`True`, M9 `"nllb"
  in`→`not in`. **7/9 survived.**
- **D6 note**: `transformers`/`torch` absent in this env — model memory
  measured by proxy (pipeline-call multiplicity) + per-model footprint
  argument, not `tracemalloc` of real weights.
- **D7**: single-threaded by construction — CLI is one-shot; ssg calls
  `variants()` serially per build; watchdog rebuild is synchronous in its
  handler thread. `_pipeline()` TOCTOU worst case is a redundant model load.

## Gaps promoted

| Gap ID | Severity | One-line |
|---|---|---|
| G-103 | S3 | `translate` ignores `target_locale` for non-NLLB models — silent pt output for any other locale |
| G-104 | S1 | evaluator declares PASSED on missing/absent/divergent input — false-green gate |
| G-105 | S2 | per-instance model load × per-locale factory → N copies co-resident + reload every rebuild |
| G-106 | S3 | `max_new_tokens` 128 cap silently truncates >32-word sentences |
| G-107 | S3 | unmapped locale passed raw as invalid FLORES `tgt_lang` |
| G-108 | S3 | missing `[transformers]` extra → bare `ModuleNotFoundError` names no remediation |
| G-109 | S3 | `ssg-i18n-evaluate main()` catches nothing — traceback on every error path |
| G-110 | S3 | catalog path silently skipped when absent; non-dict/empty catalog → AttributeError/misleading BLEU failure |
| G-111 | S3 | BLEU sentence filter hardcodes `"Start with"`/`"The collector"` excludes |
| G-112 | S3 | `extract_text_nodes` drops Quote/SetextHeading/Jinja paragraphs — evaluation blind spots |
| G-113 | S3 | four dead `is_*` helpers alive only via the `evaluator.py` re-export |
| G-114 | S3 | bare `--cov` totals polluted by editable `ssg_i18n` (4th occurrence → AX-1) |
| G-115 | S3 | two ignore-comments (`type: ignore[list-item]`, `pyright …UnknownMemberType`) name no invariant |
| G-116 | S4 | 7/9 mutants survived; cli+plugin zero-coverage-invisible; two test trees; no bdd surface → AX-2 |

Session note: the backlog row's "in-memory translator" wording is stale —
`InMemoryTextTranslator` is ssg-i18n's (AU-09 inventory); nothing in this
package matches that description. Next: MA-4 remediation step — the open
S2/S3/S4 register (AU-06…AU-10 rows) promotes to `AF-*` items.
