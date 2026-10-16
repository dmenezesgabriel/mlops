# SSG

`ssg` owns generic static site generation for one content-first site. `ssg_notebook_render` is a separate optional plugin package that renders notebooks. The site config owns publishing intent and points at content collections such as machine learning projects.

## Boundaries

- `ssg.domain`: generic site concepts such as `Site`, `ContentCollection`, and `Page`.
- `ssg.application`: build and preview use cases plus stable ports.
- `ssg.infrastructure`: filesystem manifests, Markdown rendering, semantic Jinja HTML rendering, local preview server, watchdog reload, and SSG-local logging.
- `ssg_i18n`: optional site-variant plugin for locale-aware builds and translated generated sources.
- `ssg_notebook_render`: optional `.ipynb` content renderer plugin installed separately.
- `ssg_mermaid`: optional plugin that renders `mermaid` fenced blocks to inline SVG at build time.
- `projects/*`: project-specific notebooks, markdown, scripts, charts, and data science code.
- `site/site.yaml`: publishing configuration that maps project content to rendered pages and assets.

The application and domain layers must not import infrastructure or CLI adapters. The core SSG package and notebook plugin must not import MLOps packages or project packages.

## Content Directives

Markdown pages and notebook markdown cells may use asset directives. A directive
is exactly `{{ helper("arg") }}` — single- or double-quoted, optional inner
whitespace; any other `{{ … }}`/`{% … %}` text is rendered literally, never
evaluated:

```jinja2
{{ include_source("src/nyc_taxi_demand_forecasting/pipelines/features.py") }}
{{ embed_video("demo") }}
{{ embed_image("diagram") }}
```

`include_source` embeds a source panel for a file under the collection's
`source_root`; `embed_video`/`embed_image` copy a configured `assets.videos` /
`assets.images` entry into the page output and embed a media frame.

Markdown pages and notebook markdown cells may use wikilinks:

```text
[[problem-framing|Problem Framing]]
```

Markdown pages and notebook markdown cells may use GitHub alerts — a
blockquote whose first line is exactly `> [!NOTE]`, `> [!TIP]`,
`> [!IMPORTANT]`, `> [!WARNING]`, or `> [!CAUTION]` — rendered as a callout
with a per-kind icon and title:

```markdown
> [!NOTE]
> Cached files are not re-downloaded.
```

The title localizes through the variant's `i18n` extension settings
(`label_alert_note` … `label_alert_caution`); the `[!kind]` marker itself is
fixed English syntax that document translation preserves verbatim, while the
alert body translates normally.

When the `ssg-mermaid` plugin is installed, markdown pages and notebook
markdown cells may use `mermaid` fenced blocks:

````markdown
```mermaid
flowchart LR
    A[Collect] --> B[Preprocess]
```
````

The plugin renders the diagram to inline SVG at build time through a vendored
Node.js renderer (`npm ci` provisions it on first use, so `node`/`npm` must be
on the PATH at build time). The SVG embeds `var(--surface)`/`--ink` theme
references, so it follows the site palette — including the light/dark switch —
with no JavaScript; without JS the diagram is simply already drawn. Claiming
`language-mermaid` blocks happens in the `ssg.early_html_post_processors`
entry-point group, which runs before `ssg.html_post_processors` transformers
such as syntax highlighting — `entry_points()` order within a group is
unspecified, so plugins that must win a block race register there instead.
Layout-capable rendering covers flowchart, sequence, state, class, ER, pie,
and git graph diagrams; browser-layout-dependent types (notably gantt) fail
the build with a `MermaidRenderingError` rather than shipping a broken figure.

## Output

The default build renders all configured collections into one navigable static site:

```text
site/build/index.html
site/build/search-index.json
site/build/sitemap.xml
site/build/robots.txt
site/build/404.html
site/build/sw.js
site/build/assets/site.css
site/build/assets/site.js
site/build/assets/instant.js
site/build/assets/favicon.svg
site/build/<collection>/<page>.html
```

Every page `<head>` carries Open Graph tags, a `twitter:card`/`twitter:title`/`twitter:description` block, and the packaged favicon. When the optional `site.url` config sets the absolute http(s) deployment base (e.g. `https://example.github.io/site`), pages also emit `<link rel="canonical">` + `og:url` resolved per locale root — a `pt-BR` variant canonicals under `<url>/pt-BR/` — plus one `<link rel="alternate" hreflang>` per configured locale and an `x-default` pointing at the default-locale URL. When `site.url` and the optional `site.image` config are both set, the image is copied into each variant's `assets/` and emitted as `og:image` + `twitter:image` under that variant's locale root. `site.repo_url` records the source repository URL for repo-link affordances.

Each variant root also carries `robots.txt` (`User-agent: *`/`Allow: /` plus a `Sitemap:` pointer) and — only when `site.url` is set, since `<loc>` entries must be absolute — `sitemap.xml` listing the index and every page's canonical URL, so a `pt-BR` variant publishes its own sitemap under `<url>/pt-BR/`.

The same `site.url` gate activates instant navigation: every page head then carries an `ssg:sitemap` meta pointing at its variant sitemap plus a deferred `assets/instant.js` script. The script whitelists in-sitemap same-origin links, prefetches them on hover/focus, and on click fetches the page and swaps the header/shell/footer regions in place, announcing `ssg:navigated` so `site.js` re-mounts its per-page features (search, theme, scrollspy, …) on the new markup; off-sitemap links (cross-locale, external, modified clicks), anchors, and any fetch failure fall back to native navigation.

Each variant root also emits `404.html` with the full site chrome (head/header/sidebar/footer). Hosts like GitHub Pages serve it for missing paths at any depth, so when `site.url` is set every on-page URL — assets, navigation, language links, the search-index pointer — is emitted absolute under the locale root; without `site.url` they stay relative. The preview server answers missing paths with it (mkdocs `serve.py` parity).

Each variant root also emits `sw.js`, a service worker scoped to its locale tree. Its precache manifest walks the emitted variant output on disk — `sw.js` itself, nested variant roots (e.g. `pt-BR/` inside the default tree), and `*/assets/videos/` payloads are excluded — and the file paths plus bytes hash into the worker's `VERSION`, so changed output mints a fresh cache while identical rebuilds keep it. Caches are named `ssg-offline:<scope>:<version>`; the scope prefix keeps sibling-locale workers on one origin from deleting each other's caches on activation. The worker precaches on install, serves cache-first, falls back to the network on misses, and answers failed navigations with the cached 404. `site.js` registers it once per load via the `ssg:service-worker` head meta — a relative `sw.js` pointer, so unlike the sitemap gate it needs no `site.url` — and skips cleanly where the API is absent (`file://`, insecure origins) or the resolved worker URL is cross-origin.

Use `--collection <name>` only for focused local builds. Projects do not own separate sites.

## Plugin Install

Notebook rendering stays outside core. Install the plugin package instead of adding a core extra:

```bash
uv pip install ssg-notebook-render
```

Internationalization also stays outside core. Install the i18n extra for manual catalogs:

```bash
uv pip install "ssg[i18n]"
```

Install machine translation support only when build-time model translation is needed:

```bash
uv pip install "ssg[i18n-transformers]"
```

The i18n plugin translates generated Markdown and notebook markdown cells while preserving fenced code, inline code, asset directives, wikilink targets, URLs, and notebook code cells.

Translation reuse is incremental across processes: each generated file carries a `<name>.translate-fingerprint` sidecar recording the catalog fingerprint, the source SHA-256, and a hash of the translator package code. A cold build (CI, fresh checkout) skips the model work only when all three match and the output file exists, so caching `site/.ssg` between runs is safe — a stale or missing sidecar always falls back to re-translation.

Mermaid diagram rendering stays outside core as well:

```bash
uv pip install ssg-mermaid
```

## Commands

```bash
make build-site
make preview-site
```
