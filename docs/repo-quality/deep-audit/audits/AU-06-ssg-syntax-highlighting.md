# AU-06 — ssg-syntax-highlighting audit (2026-10-01)

MA-4 step 1. Target: `libs/ssg-syntax-highlighting` — 229 LOC / 181 SLOC per
radon raw; 27 blocks, avg complexity A 2.07, max B(6)
`CodeBlockHtmlParser.handle_starttag`, MI all A. Gates baseline: pyright
strict 0 errors, 12 tests pass, coverage 100% (floor 95, post-QH-3). The
plugin highlights fenced code blocks by round-tripping each rendered page
body through `HTMLParser` — so the audit weight sits on serialization
fidelity (D1) and assertion strength (D9).

Reused verdicts (not re-audited): entry-point contract — `ssg` loads
`ssg.html_post_processors` via `_load_plugin` and isinstance-checks against
`@runtime_checkable HtmlPostProcessor` (AU-05/AF-29; installed `pygments` EP
verified conforming); invocation site — `StaticSiteBuilder` runs
post-processors per *page body fragment* before Jinja wraps it
(`static_site_builder.py:292-297`), so doctype/head markup never reaches the
parser; extension settings — `SiteConfigRepository` rejects non-str keys and
non-str values at load (`site_config_repository.py:243-284`), so
`style: 42` is unreachable from real config.

Liveness probe: `MarkdownIt("commonmark").render("```python\nx\n```")` emits
`<pre><code class="language-python">x\n</code></pre>` — the plugin's trigger
shape is what the real renderer produces (unpinned by any test — G-60).

## Surface inventory

| Module | LOC | Public symbols | Entry |
|---|---|---|---|
| `application/syntax_highlighter.py` | 157 | `CodeBlockSyntaxHighlightingProcessor.process`★, `CodeBlockHtmlParser` (+`handle_*` callbacks), `CodeSyntaxHighlighter`, `CodeSyntaxHighlighterFactory` ports | `ssg.html_post_processors` group → `plugin.create_pygments_html_post_processor` |
| `infrastructure/pygments_highlighter.py` | 57 | `PygmentsCodeSyntaxHighlighter.highlight`, `PygmentsCodeSyntaxHighlighterFactory.create` | injected into processor |
| `infrastructure/plugin.py` | 14 | `create_pygments_html_post_processor`★ | `[project.entry-points."ssg.html_post_processors"] pygments` (pyproject:10-11) |

## Callgraph

```
(importlib.metadata entry point, cli.py:181)
create_pygments_html_post_processor                       [plugin.py:10]
  → CodeBlockSyntaxHighlightingProcessor(
        PygmentsCodeSyntaxHighlighterFactory())

per page body, static_site_builder.py:295:
process(rendered_html, site)                              [syntax_highlighter.py:29]
  ├─ "language-" not in html → early return               [:32]
  ├─ site.extension_setting("syntax_highlighting","style","gruvbox-dark") [:35]
  ├─ factory.create(style_name) → PygmentsCodeSyntaxHighlighter
  │     └─ HtmlFormatter(nowrap=True, noclasses=True, style=style_name)  [per call]
  ├─ CodeBlockHtmlParser(highlighter).feed/close          [:38-40]
  │   ├─ handle_starttag: <pre>→_inside_pre=True; <code class=language-*>
  │   │   inside pre → capture mode (tag itself already emitted)  [:67-83]
  │   ├─ handle_data → code_fragments if capturing else fragments [:101]
  │   ├─ handle_entityref/handle_charref → re-emit verbatim       [:108-113]
  │   │   (unreachable under convert_charrefs=True — see D4 note)
  │   ├─ handle_endtag </code> in capture → _append_highlighted_code:
  │   │   html.unescape(code) → highlighter.highlight(src, lang)  [:85-125]
  │   │   then "</code>" re-emitted; </pre> → _inside_pre=False
  │   └─ NOT overridden: handle_startendtag, handle_comment,
  │       handle_decl, handle_pi, unknown_decl, handle_data-CDATA split
  └─ LOGGER.info(syntax_highlighting_finished, highlighted_blocks)
pygments path: get_lexer_by_name(language) — ClassNotFound → TextLexer
  fallback → highlight(source, lexer, formatter) →
  .replace("<span ", '<span class="highlight-token" ')   [pygments_highlighter.py:27-31]
```

Dead-looking: none module-level. `handle_entityref`/`handle_charref` are
unreachable through `feed()` under `convert_charrefs=True` (stdlib probing in
QH-3 showed script/style content arrives via `handle_data`) — kept +
test-pinned as a convert_charrefs=False forwarding contract. Design note,
not a row: no demonstrated harm; the pair is what makes the M4 flag flip a
pure equivalent mutant (below).

## Boundary table

| Boundary | Where | Faked as | Test |
|---|---|---|---|
| `pygments` lib (`highlight`, `HtmlFormatter`, `get_lexer_by_name`) | pygments_highlighter.py:5-11 | `RecordingHighlighter` named fake at the `CodeSyntaxHighlighter` port | test_code_block_html_parser.py ×7 (fake) + test_syntax_highlighting.py ×5 (real pygments) |
| `Site.extension_setting` config read | syntax_highlighter.py:35-38 | real `Site` entity | configured-style test (monokai `#66D9EF`) ✓ |
| entry-point loading | ssg cli.py:181-190 | ssg-side `FakeEntryPoint` + isinstance check | ssg suite (AF-29); EP conformance verified live |
| logging (`LOGGER.info` ×2 sites) | syntax_highlighter.py:41, pygments_highlighter.py:38,46 | not asserted | uncovered-by-assertion (M5 survived) |
| fs / network / subprocess / env / RNG | none in scope | — | — |

## Dimension findings

| Dim | Suspect / measured | Evidence | Disposition |
|---|---|---|---|
| D1 | **Phantom end tags for self-closing elements**: no `handle_startendtag` override → default calls `handle_starttag`+`handle_endtag` → `<br/>` emits `<br></br>` (browsers parse stray `</br>` as a second `<br>` → doubled break), `<hr/>`→`<hr></hr>`, `<img/>`→`<img/>`+`</img>`, `<input/>`→phantom `</input>`. **Reachable via ordinary markdown**: `MarkdownIt` emits `<br />` for hard breaks (`a  \nb`), and raw-HTML passthrough carries author `<hr/>`/`<img/>`. Amplified by the substring trigger: `"language-"` anywhere (e.g. prose *documenting* `language-python`) re-serializes the whole page — probe: `<p>Use language-python classes<br />here</p>` → `<br></br>` with **zero code blocks** | syntax_highlighter.py (no `handle_startendtag`); probes P1/P2 | **G-55 S3** |
| D1 | **Comments, declarations, PIs silently dropped**: no `handle_comment`/`handle_decl`/`handle_pi`/`unknown_decl` → `<!-- c -->` + `language-` trigger → comment gone; `<?xml v?>` gone; `<!DOCTYPE x>` gone (bounded — doctype never reaches fragment scope; author raw-HTML comments do). Content loss with zero signal | probes P3/P4/P5 | **G-56 S3** |
| D1 | **Double entity decode into the lexer**: `convert_charrefs=True` already decodes data; `_append_highlighted_code` runs `html.unescape` again → authored code `&amp;` (HTML `&amp;amp;`) reaches the lexer as `&` — displayed code changes (`a &amp; b` → `a & b` highlighted). Constraint measured: CDATA-nested `<script>` inside `<code>` arrives *undecoded* → unescape is load-bearing there; fix must split by arrival mode or move to `convert_charrefs=False` + uniform raw capture (the M4-equivalent mode) | syntax_highlighter.py:115-117; probes P6/P7 | **G-57 S3** |
| D1 | **Unclosed `<code>` capture drops buffered source**: `<pre><code class="language-python">unclosed` (EOF) → output ends `<code class="language-python">` — captured text in `_code_fragments` never flushed at `close()`. Malformed-input bounded (markdown-it always closes; raw-HTML only), but silent content loss | probe P8 | **G-58 S3** |
| D2 | **Per-page highlighter + per-block lexer construction**: `factory.create(style)` builds `HtmlFormatter` inside `process()` — 205 µs/call vs 340 µs for a 1-block page (~60%); `get_lexer_by_name` 58 µs/block. Scaling: 10/50/200 blocks → 3.23/10.12/29.81 ms (linear, ~150-320 µs/block amortized) — no asymptotic issue; the constant is per-page waste on a per-build-invariant style (G-52 class: env-per-page measured S3 there). At n=2000 pages ≈410 ms pure reconstruction | syntax_highlighter.py:35-39, pygments_highlighter.py:23-25; timeit | **G-59 S3** |
| D1 | **Style validated on first code-bearing page**: `extensions.syntax_highlighting.style: bogus` → `ClassNotFound` (a `ValueError`) raised inside `process` mid-build → pages already written stay; `main()`'s SystemExit catch (AF-29) keeps the exit clean but the message names `pygments.styles.bogus`, not the `syntax_highlighting.style` setting. Non-str values unreachable (repository rejects at load) | probe P9 + site_config_repository.py:271-284 | **G-61 S3** |
| D9 | **Assertion-weak suite at 100% line coverage — 5/5 mutants survived**: M1 `len>→>=` (bare `language-` class captures), M2 `_inside_pre` guard removal (code outside `<pre>` highlights), M3 `html.unescape` drop (entity path unasserted), M4 `convert_charrefs=True→False` (invisible — entityref/charref re-emit verbatim; equivalent-mutant pair), M5 `highlighted_blocks += 1`→`pass` (log counter unasserted). **Plus**: no test drives real `MarkdownIt` output through `process()` — plugin liveness is by-construction only (fence output shape verified by probe today; a drift would silently no-op) | mutation run M1–M5 | **G-60 S4** |
| D7 | Shared processor across threads: 8 threads × 150 `process()` calls on one instance → 0 output mismatches. Per-call parser; shared state is an immutable style name + stateless factory | stress probe | clean (measured) |
| D6 | `tracemalloc` 300-call rounds → +360/+365/+368 KB at 300/600/900 then −3 KB net for round 4 — bounded pygments warm-up (formatter style/lexer caches), not per-call growth | tracemalloc probe | clean (measured) |
| D8 | Pygments escapes code content (`&lt;span x&gt;` stays `&lt;`), so the `<span `→`class=` injection only rewrites formatter-owned markup; attrs re-escaped via `html.escape(quote=True)`; no injection/pickle/subprocess surface | probe P10 + reading | clean |
| D3 | File-scoped pyright pragmas on the pygments boundary carry the invariant comment (missing stubs for `lexers.special`); `HtmlFormatter[str]` annotated; `extension_setting` returns honest `str` | pygments_highlighter.py:1-2 | clean |
| D4 | Port+factory indirection earns its place (test fakes the port; pygments is the seam). Dead callbacks note above | reading | clean / note |
| D5 | Specific names, predictable `application`/`infrastructure` split, 157-LOC max file | reading | clean |
| D10 | No `features/`/bdd — plugin surface is exercised via unit `process()` only; the `build` user surface is already AX-2-tagged (AU-04 disposition) | find tests/ | folded into G-60 |

## Measurements

- **P1** `<hr/><img src="a.png"/><input/><pre><code class="language-x">y</code></pre>` → `<hr></hr><img src="a.png"></img><input type="text"></input>…` (phantom end tags on every self-closing element; `language-x` unknown → TextLexer passthrough `y\n`).
- **P2** `<p>Use language-python classes<br />here</p>` → `<br></br>` — prose-only trigger, no code block.
- **P3** `<!-- c --><p>language-x</p>` → `<p>language-x</p>` — comment gone.
- **P4** `<?xml v?>…`, **P5** `<!DOCTYPE x>…` → dropped.
- **P6** `<code class="language-text">a &amp;amp; b</code>` → lexer receives `a & b` (authored `&amp;` corrupted).
- **P7** `<code class="language-text"><script>a &amp; b</script>tail &amp;x</code>` → CDATA raw `&amp;` undecoded at capture → unescape load-bearing on this path (source `a & b…&x` correct).
- **P8** `<pre><code class="language-python">unclosed` → output `<pre><code class="language-python">` — source dropped.
- **P9** `style: bogus` → `ClassNotFound: Could not find style module 'pygments.styles.bogus'` at first `process()` call (isinstance ValueError → `main()` SystemExit covers).
- **P10** code containing `&lt;span x&gt;` → output `&quot;&lt;span x&gt;&quot;` — escaped, replace-safe.
- **D2 timeit**: `HtmlFormatter` ctor 205 µs; `get_lexer_by_name` 58 µs; `process` 1-block page 340 µs; 10/50/200 blocks → 3.23/10.12/29.81 ms (linear); prose-only trigger 0.94 ms vs 0.0015 ms fast-path for identical page without `language-`.
- **D6 tracemalloc**: +360 KB @300 calls, +368 KB @900, round-over-round −3 KB — bounded cache warm-up.
- **D7**: 8 threads × 150 calls → 0 mismatches.
- **D9 mutations**: 5 flips, all SURVIVED — M1 `len>→len>=`, M2 `_inside_pre` drop, M3 `unescape` drop, M4 `convert_charrefs` flip (equivalent — re-emitting callbacks preserve output), M5 counter `+=1`→`pass`.
- **Coverage**: 208 stmts, 0 miss, 100% (post-QH-3 `source=["src","tests"]`).

## Gaps promoted

| Gap ID | Severity | One-line |
|---|---|---|
| G-55 | S3 | `handle_startendtag` not overridden → `<br/>`→`<br></br>` doubles breaks; every self-closing element gets a phantom end tag; prose-`language-` pages corrupted too |
| G-56 | S3 | Comments/declarations/PIs dropped — no `handle_comment`/`handle_decl`/`handle_pi`/`unknown_decl` overrides |
| G-57 | S3 | `html.unescape` double-decodes charref-converted data (authored `&amp;` → `&`); needed only for CDATA-nested script/style |
| G-58 | S3 | Unclosed `<code>` capture drops buffered source silently at `close()` |
| G-59 | S3 | `HtmlFormatter`+lexer rebuilt per page/block — 205 µs ctor vs 340 µs 1-block page (~60%), ~410 ms @ n=2000 |
| G-61 | S3 | `syntax_highlighting.style` typo → `ClassNotFound` mid-build (partial output written; message names pygments internals, not the config setting) |
| G-60 | S4 | 5/5 mutants survived at 100% coverage (parser guards + unescape + charrefs flag + counter unasserted); no real-`MarkdownIt`-output integration test — liveness by construction only |

## Notes for AU-07/AU-08

`ssg-latex` (AU-07) is the sibling `ssg.html_post_processors` EP — if it also
round-trips HTML through a parser, expect the G-55/G-56/G-58 classes there;
if it regex-rewrites, different suspects. `ssg-notebook-render` (AU-08)
already flags the G-42/G-43/G-49/G-52 transclusion-pipeline copy; its
renderer output also passes through *this* processor when installed — the
`<br/>` corruption applies to notebook-rendered pages equally.
