# AU-07 — ssg-latex audit (2026-10-01)

MA-4 step 2. Target: `libs/ssg-latex` — 280 LOC / ~119 SLOC (latex_processor)
per radon raw; 24 blocks, avg complexity A 2.21, all A. Gates baseline:
pyright strict 0 errors, 14 tests pass, coverage 78.29% — but the denominator
is polluted by the editable `ssg` workspace dep (no `[tool.coverage.run]
source=`); own modules measure `latex_processor.py` 95% (misses exactly the
five verbatim-emit handlers :113,:116,:119,:122,:125),
`subprocess_renderer.py` 91% (:62, :92-93). The plugin renders `$…$`/`$$…$$`
math in page body fragments by round-tripping HTML through `HTMLParser` +
spawning `npx katex` per unique expression — audit weight on entity handling
(D1), serialization fidelity (D1), subprocess cost (D2), and the npm-install
boundary (D8).

Reused verdicts (not re-audited): EP contract — `ssg` loads
`ssg.html_post_processors` via `_load_plugin` + isinstance against
`@runtime_checkable HtmlPostProcessor` (AU-05/AF-29; conformance verified live
below — the plugin loaded and processed a real build); invocation — processors
run per **page body fragment** at `static_site_builder.py:283-297`, head/layout
wrapped later by `_page_renderer.render_page` (so `</head>` can never appear
in input); extension settings load-validated (`site_config_repository.py`).

## Surface inventory

| Module | LOC | Public symbols | Entry |
|---|---|---|---|
| `application/latex_processor.py` | 167 | `LatexHtmlPostProcessor.process`★, `LatexHtmlParser` (+`handle_*`), `LatexRenderer` (Protocol), `LatexRenderingError`, `MATH_PATTERN`, `_escape_text_underscores` | `ssg.html_post_processors` → `plugin.create_latex_html_post_processor` |
| `infrastructure/subprocess_renderer.py` | 98 | `SubprocessLatexRenderer.render`, `._ensure_setup` | injected into processor |
| `infrastructure/plugin.py` | 15 | `create_latex_html_post_processor`★ | `[project.entry-points."ssg.html_post_processors"] latex` (pyproject:10) |

## Callgraph

```
(importlib.metadata entry point, ssg cli.py)
create_latex_html_post_processor                       [plugin.py:11]
  → SubprocessLatexRenderer(package_dir=src/ssg_latex)
  → LatexHtmlPostProcessor(renderer)   [_cache dict born here — per build]

per page body fragment, static_site_builder.py:295:
process(rendered_html, site)                           [latex_processor.py:135]
  ├─ LatexHtmlParser(self._cached_render) — convert_charrefs=False  [:64,136]
  │   ├─ handle_starttag: non-void tags push _tag_stack;
  │   │   emit get_starttag_text() verbatim                [:73-79]
  │   │   (NOT overridden: handle_startendtag — default calls
  │   │    starttag+endtag → phantom end tags, see P2)
  │   ├─ handle_endtag: pop-to-match _tag_stack;
  │   │   emit f"</{tag}>" unconditionally                  [:81-88]
  │   ├─ handle_data: skip when stack ∩ {pre,code,script,
  │   │   style,textarea}; else MATH_PATTERN.split → odd parts
  │   │   rendered via _render_fn (data splits at entities — P1)  [:90-110]
  │   ├─ handle_comment/decl/pi/entityref/charref:
  │   │   re-emit verbatim (all uncovered — cov :113-125)
  │   └─ unknown_decl NOT overridden → <![CDATA[…]]> dropped (P7)
  ├─ _cached_render → renderer.render(expr, display)    [:160-167]
  │     └─ SubprocessLatexRenderer.render                 [subprocess_renderer.py:21]
  │         ├─ _ensure_setup: which(node),which(npm);
  │         │   node_modules missing → `npm install` in package_dir [:60-98]
  │         └─ subprocess.run(npx --prefix pkg --no-install katex [-d],
  │             input=expr) → rc!=0 → LatexRenderingError [:24-58]
  └─ math_rendered → search `</head>` in fragment (never present —
      dead branch) → fallback appends <link> at fragment end [:142-156]
```

Dead-looking: `head_pattern`/`</head>`-inject branch (:149-153) — unreachable
via the only production caller (fragments have no `</head>`); reachable only
in tests feeding full documents.

## Boundary table

| Boundary | Where | Faked as | Test |
|---|---|---|---|
| `npx`/`node` subprocess (katex CLI) | subprocess_renderer.py:44-50 | `MagicMock` patching `subprocess.run` — no injectable runner seam | test_subprocess_renderer.py ×4 |
| `npm install` into package dir | subprocess_renderer.py:86-91 | same MagicMock | `test_renderer_runs_npm_install…` |
| PATH env (`shutil.which` node/npm) | subprocess_renderer.py:65,72 | `patch("shutil.which")` | node/npm-missing tests ×2 |
| fs `node_modules` exists | subprocess_renderer.py:80 | `patch.object(Path,"exists")` | both branches covered |
| network — npm install + CDN css url | :86-91; config `katex_css_url` | — | latent (vendored node_modules) |
| `Site.extension_setting` | latex_processor.py:143 | real `Site` entity | css-url test ✓ |
| entry-point loading | ssg cli.py | ssg-side (AF-29) | EP conformance verified live (tmp site build ran processor) |
| logging `LOGGER.info` ×2 | subprocess_renderer.py:34,81 | not asserted | — |

## Dimension findings

| Dim | Suspect / measured | Evidence | Disposition |
|---|---|---|---|
| D1 | **Entities split math → silent no-render**: `convert_charrefs=False` fires `handle_entityref`/`handle_charref` between `handle_data` chunks; `MATH_PATTERN.split` runs per chunk → `$a < b$` (markdown emits `&lt;`), `$x &amp;= y$`, `$a > b$` never match. Real build: `out/coll/overview.html` contains literal `$a &lt; b$`; renderer never called; `math_rendered` stays False → no CSS, zero signal. `<`, `>`, `&` are among the most common math characters | latex_processor.py:64,96; P1 + live build | **G-62 S1** |
| D1 | **`handle_startendtag` not overridden → phantom end tags**: default calls starttag+endtag; `handle_endtag` emits `</{tag}>` unconditionally → `<br/>`→`<br/></br>` (browser parses `</br>` as a second `<br>` — doubled break; markdown hard breaks emit `<br />`), `<hr/>`→`<hr/></hr>`, `<img/>`→`<img/></img>`. Non-void variant beyond G-55's scope: `<div/>x`→`<div/></div>x` — trailing content moves *out* of the div (browser treats `<div/>` as open) | no `handle_startendtag`; P2 | **G-63 S3** |
| D1/D4 | **`</head>` injection is dead code; `<link>` lands inside body**: `process()` input is a body fragment (static_site_builder.py:283-297) → `</head>` never matches (:150) → fallback appends the stylesheet at fragment end. Live build: `<link rel=stylesheet …>` sits inside `</article>` before the pager nav — late-loading CSS (FOUC), not the intended head placement. Two tests pin the dead branch with full documents | latex_processor.py:149-156; live build | **G-64 S3** |
| D1 | **`LatexRenderingError` escapes `main()`'s catch** → raw traceback mid-build: `class LatexRenderingError(Exception)` (:48) is not in cli.py:47-53's `(ValueError, TypeError, FileNotFoundError, ImportError, RuntimeError)`. Live: `$\frac{1}{$` → rc=1 + full Python traceback + katex's multi-line stderr embedded in the message; `out/index.html` written, `out/coll/` absent — partial build | P5 + live build | **G-65 S3** |
| D2 | **~5× npx overhead per unique expression**: `npx --prefix … --no-install katex` 700-780 ms/call (shell n=3 2.108 s, timeit n=5 780 ms) vs `node node_modules/katex/cli.js` 140 ms/call (n=3 419 ms) — ~560 ms npm machinery per spawn. Cost is linear in *unique* expressions (`_cache` dedupes repeats only): 200 unique ≈ 2.4 min vs 28 s direct; a single-persistent-process or batch interface would collapse to ~ms/expr | subprocess_renderer.py:24-50; timeit | **G-66 S2** |
| D8/D1 | **`npm install` into the installed package dir at build time**: `cwd=package_dir` writes `node_modules` inside site-packages, needs network, runs dependency lifecycle scripts; only fires when the vendored dir is absent (latent today — `src/ssg_latex/node_modules` ships katex 0.17.0 + package-lock). `npm ci --ignore-scripts` is the deterministic shape; failing that, a read-only install should fail fast with a named error | subprocess_renderer.py:79-96 | **G-67 S3** |
| D1 | **`_escape_text_underscores` no-ops on nested braces → katex abort**: `\\text\{([^{}]*)\}` can't match `\text{a_{b}}` (inner `{` excluded) → `_` unescaped → real katex → `ParseError: Can't use function '_'` → `LatexRenderingError` → traceback (chains into G-65) | latex_processor.py:45; P6 + real render | **G-70 S3** |
| D1 | **`unknown_decl` not overridden → `<![CDATA[x]]>` silently dropped**: `<![CDATA[payload]]>` input → empty output; bogus-markup content loss with no signal (bounded — CDATA is bogus markup in HTML; author raw-HTML passthrough only) | no `unknown_decl`; P3 | **G-71 S3** |
| D9 | **Coverage denominator polluted + floor below sibling convention**: bare `--cov` traces editable `ssg` — report shows ssg's static_site_builder.py 28%, site.py 48% etc. inflating TOTAL to 677 stmts; own modules are 91-95%. Missing `[tool.coverage.run] source=["src","tests"]` (sibling ssg-syntax-highlighting pyproject:16-17 pattern + comment); floor 75 vs sibling 95 | pyproject.toml (absent), coverage report | **G-68 S3** |
| D9 | **Assertion-weak on fidelity paths — 2/6 mutants survived + all 5 emit handlers uncovered**: M3 `tag_lower in _tag_stack` guard removal SURVIVED (mis-nest/pop tracking unasserted); M5 `convert_charrefs=False→True` SURVIVED (no entity-bearing test — the flip would *fix* G-62 for data but corrupt non-math fragments); coverage misses :113,:116,:119,:122,:125 (comment/decl/pi/entityref/charref verbatim emitters — trivially surviving mutants). No currency `$10-$20` passthrough test (M2's flip died via `$t+1$`, not the guard itself). `test_plugin.py` asserts privates `._renderer._package_dir`; subprocess tests MagicMock-patch the boundary — no injectable runner (named-fake rule) | mutation run; cov report | **G-69 S4** |
| D6 | `_cache` unbounded dict keyed `(expr, display)` — measured bounded: +85-89 KB per 300 unique exprs (fake renderer); real KaTeX ~1.1-4 KB output/expr → ~1 MB/300 real renders; per-build lifetime, unique-expression bound | P8 tracemalloc | clean (measured bounded) |
| D7 | `_cache`/`_verified` shared across `process()` calls — single-threaded by construction: processors run in a sequential loop (static_site_builder.py:294-295); no consumer parallelizes | code path | clean (written claim) |
| D3 | `Callable[[str,bool],str]` render seam, `dict[tuple[str,bool],str]` cache — explicit, no casts; `attrs` unused (vulture `ignore_names` carries the stdlib-signature comment); `get_starttag_text() or f"<{tag}>"` fallback drops attrs — unreachable via `feed()` | reading | clean |
| D4 | `LatexRenderer` port earns its place (FakeLatexRenderer in tests; subprocess adapter is the real seam); protocol-inheritance idiom matches sibling | reading | clean |
| D5 | Specific names, predictable application/infrastructure split, ≤167-LOC files | reading | clean |
| D8 | expression → npx stdin (no shell, fixed argv) ✓; katex stderr embedded raw into exception message (node stack in user-facing error — message-shape nit folded into G-65 evidence); `katex_css_url` interpolated unquoted into `<link href>` — author-committed config boundary (G-04 convention) | reading | note |
| D10 | No `features/`/bdd — plugin surface exercised via `process()` unit tests + this session's live-build probe; the `build` user surface already AX-2-tagged (AU-04) | find tests/ | folded into G-69 |

## Measurements

- **P1 (entity split)**: `process("<p>When $a &lt; b$ holds</p>")` → output identical, `render` calls = 0; same for `&amp;`, `&gt;`. `&#36;y$` correctly can't open math. Live build (`/tmp/au07site`): markdown `$a < b$` → `out/coll/overview.html` contains literal `$a &lt; b$`.
- **P2 (startendtag)**: `<p>a<br />b</p>` → `<p>a<br /></br>b</p>`; `<hr/><img/><input/>` → each +phantom end tag; `<div/>tail` → `<div/></div>tail`.
- **P3**: `<b><i>x</b></i>` round-trips faithfully (pop-to-match); `<![CDATA[payload]]>` → `''`; `<div>x</div foo>` → `<div>x</div>` (end-tag attrs stripped); unclosed `<pre><code>…` content preserved (G-58 absent here).
- **P4**: `<pre><code>$not$</code></pre>` + `<p>$yes$</p>` → only `yes` rendered — ignored-tags hold.
- **P5 (exception escape)**: `issubclass(LatexRenderingError, RuntimeError)` = False. Live build with `$\frac{1}{$` → rc=1, `Traceback …` + `LatexRenderingError` (katex stderr with full node stack embedded); `out/index.html` written, `out/coll/` absent.
- **P6 (nested \text)**: `\text{a_{b}}` sent to renderer unescaped (`calls=[('\\text{a_{b}}',…)]`); real render → `LatexRenderingError` (KaTeX ParseError on `_` in text mode). `\text{a_b}` → `\text{a\_b}` (escape works on flat case).
- **P7**: `<![CDATA[payload]]>` alone → `''`.
- **P8 tracemalloc**: `_cache` +88/82/89 KB per +300 unique exprs — bounded by unique-expression count.
- **D2 timeit**: npx path 780 ms/call (n=5), shell loop 2.108 s/3 ≈ 700 ms; `node cli.js` direct 419 ms/3 ≈ 140 ms/call → ~5× / ~560 ms npm overhead per spawn.
- **Mutations** (ephemeral flips on latex_processor.py, reverted — `git status` clean): KILLED — M1 `i%2==1→0`, M2 `(?!\d)→(?=[a-z])`, M4 `math_rendered→pass`, M6 slice swap; SURVIVED — M3 tag-stack pop-guard removal, M5 `convert_charrefs→True`.
- **Coverage**: `--cov` TOTAL 78.29% (677 stmts incl. ~550 ssg-pollution); `latex_processor.py` 95% miss :113,116,119,122,125; `subprocess_renderer.py` 91% miss :62,92-93; floor 75.
- **Live build EP check**: `python -m ssg.infrastructure.cli build` on tmp site → `subprocess_latex_renderer_rendering` logs ×2, KaTeX spans in output — EP conforms and fires (AF-29 contract live-verified).

## Gaps promoted

| Gap ID | Severity | One-line |
|---|---|---|
| G-62 | S1 | Entity refs split `handle_data` chunks → `$a < b$`/`$x & y$`/`$a > b$` silently never render (0 calls, no CSS, literal `$…$` in output) |
| G-63 | S3 | `handle_startendtag` missing → `</br>` phantom doubles breaks; `<div/>`→`<div/></div>` moves tail out of div; end-tag attrs stripped (`</div foo>`→`</div>`) |
| G-64 | S3 | `</head>` injection dead in production (fragments have no head) → KaTeX `<link>` lands inside `</article>`; two tests pin the dead branch |
| G-65 | S3 | `LatexRenderingError(Exception)` escapes `main()`'s catch tuple → full traceback + embedded node stack; partial output written |
| G-66 | S2 | `npx` spawn per unique expression ~700-780 ms vs `node cli.js` ~140 ms — ~5× overhead; 200 unique exprs ≈ +2 min |
| G-67 | S3 | `_ensure_setup` runs `npm install` (network + lifecycle scripts) cwd'd inside the installed package dir when vendored node_modules is absent |
| G-68 | S3 | No `[tool.coverage.run] source=` → editable `ssg` pollutes the denominator (78% vs own-module 91-95%); floor 75 vs sibling 95 |
| G-69 | S4 | Emit handlers :113-125 uncovered; M3/M5 mutants survived; no entity/currency passthrough test; private-attr asserts + MagicMock boundary patches |
| G-70 | S3 | `\\text\{([^{}]*)\}` can't match `\text{a_{b}}` → unescaped `_` → KaTeX ParseError → G-65 traceback |
| G-71 | S3 | `unknown_decl` missing → `<![CDATA[x]]>` silently dropped |

## Notes for AU-08+

`ssg-notebook-render` (AU-08) output passes through this processor when
installed — notebook cells emitting `<`/`&`-laden math hit G-62 identically;
cell HTML with self-closing tags hits G-63. The G-62 fix shape (buffer text
runs across entity events, then `MATH_PATTERN.split` once per run) preserves
the verbatim entity fidelity this package gets right — `convert_charrefs=True`
alone would decode entities into non-math fragments and corrupt them (M5
mutant proves the flip survives today's suite, so any fix must pin both
directions).
