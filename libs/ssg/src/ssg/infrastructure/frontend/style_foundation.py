FONT_IMPORTS = """
@import url("https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&family=Newsreader:opsz,wght@6..72,400;6..72,600;6..72,800&display=swap");
""".strip()


DESIGN_TOKENS = """
:root {
  color-scheme: light;
  --paper: #f3ead8;
  --paper-deep: #e3d3b8;
  --surface: #fff9eb;
  --surface-muted: #eadfca;
  --ink: #15110d;
  --ink-soft: #443a2f;
  --muted: #756852;
  --border: #15110d;
  --taxi: #f2bd22;
  --signal: #df5035;
  --cyan: #2da8a0;
  --green: #5f8f3f;
  --focus: #0a6cff;
  --shadow-hard: 0.55rem 0.55rem 0 var(--ink);
  --shadow-soft: 0 1.4rem 4rem rgb(21 17 13 / 0.14);
  --font-display: "Newsreader", Georgia, "Times New Roman", serif;
  --font-body: "IBM Plex Sans", Verdana, Geneva, sans-serif;
  --font-mono: "IBM Plex Mono", "Courier New", monospace;
  --measure: 72ch;
  --wide-measure: 94ch;
  --radius: 1.1rem;
  --speed: 220ms;
}
""".strip()


RESET_STYLES = """
*, *::before, *::after { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body, h1, h2, h3, p, figure, blockquote, dl, dd { margin: 0; }
img, video, svg { display: block; max-width: 100%; }
button, input, textarea, select { font: inherit; }
""".strip()


BASE_STYLES = """
body {
  background:
    radial-gradient(circle at 18% 12%, rgb(242 189 34 / 0.2), transparent 28rem),
    radial-gradient(circle at 90% 18%, rgb(45 168 160 / 0.14), transparent 24rem),
    linear-gradient(90deg, rgb(21 17 13 / 0.045) 1px, transparent 1px),
    linear-gradient(180deg, rgb(21 17 13 / 0.035) 1px, transparent 1px),
    radial-gradient(rgb(21 17 13 / 0.022) 0.7px, transparent 0.7px),
    var(--paper);
  background-size: auto, auto, 3.2rem 3.2rem, 3.2rem 3.2rem, 5px 5px, auto;
  color: var(--ink);
  font-family: var(--font-body);
  font-size: clamp(1rem, 0.96rem + 0.18vw, 1.12rem);
  line-height: 1.68;
  min-height: 100vh;
}

a {
  color: var(--ink);
  text-decoration-color: var(--signal);
  text-decoration-thickness: 0.12em;
  text-underline-offset: 0.18em;
}

a:hover { color: var(--signal); }
a:focus-visible, button:focus-visible { outline: 4px solid var(--focus); outline-offset: 4px; }
::selection { background: var(--taxi); color: var(--ink); }
""".strip()


UTILITY_STYLES = """
.cluster { align-items: center; display: flex; flex-wrap: wrap; gap: 0.75rem 1rem; }
.stack > * + * { margin-top: clamp(1rem, 2vw, 1.5rem); }
.breakout, .wide-figure { max-width: var(--wide-measure) !important; }
.mono { font-family: var(--font-mono); }
.visually-hidden {
  clip: rect(0 0 0 0);
  clip-path: inset(50%);
  height: 1px;
  overflow: hidden;
  position: absolute;
  white-space: nowrap;
  width: 1px;
}
.data-label, .eyebrow, .kicker {
  font-family: var(--font-mono);
  font-size: 0.76rem;
  font-weight: 600;
  letter-spacing: 0.12em;
  line-height: 1.2;
  text-transform: uppercase;
}
.eyebrow { color: var(--signal); }
.data-label { color: var(--cyan); }
.lede {
  color: var(--ink-soft);
  font-family: var(--font-display);
  font-size: clamp(1.25rem, 1rem + 1vw, 1.85rem);
  line-height: 1.28;
  max-width: 42rem;
}
""".strip()


LAYOUT_STYLES = """
.skip-link {
  background: var(--ink);
  border: 2px solid var(--taxi);
  color: var(--surface);
  left: 1rem;
  padding: 0.75rem 1rem;
  position: absolute;
  top: 1rem;
  transform: translateY(-150%);
  z-index: 40;
}
.skip-link:focus { transform: translateY(0); }

.site-header {
  align-items: stretch;
  background: rgb(243 234 216 / 0.92);
  border-bottom: 3px solid var(--ink);
  display: grid;
  gap: 1rem;
  grid-template-columns: auto minmax(0, 1fr) auto;
  padding: 0.85rem clamp(1rem, 4vw, 3rem);
  position: sticky;
  top: 0;
  z-index: 20;
}

@supports (backdrop-filter: blur(14px)) {
  .site-header { backdrop-filter: blur(14px); }
}

.masthead-mark {
  align-items: center;
  background: var(--taxi);
  border: 3px solid var(--ink);
  display: grid;
  font-family: var(--font-mono);
  font-size: 0.9rem;
  font-weight: 600;
  min-height: 3.2rem;
  padding: 0 0.8rem;
  transform: rotate(-2deg);
}

.site-title {
  color: var(--ink);
  display: inline-block;
  font-family: var(--font-display);
  font-size: clamp(1.45rem, 1rem + 1.5vw, 2.25rem);
  font-weight: 800;
  line-height: 0.95;
  text-decoration: none;
}
.site-description {
  color: var(--muted);
  font-size: 0.95rem;
  line-height: 1.25;
  margin-top: 0.25rem;
}
.menu-toggle {
  align-self: center;
  background: var(--ink);
  border: 3px solid var(--ink);
  color: var(--surface);
  cursor: pointer;
  display: none;
  font-family: var(--font-mono);
  font-weight: 600;
  padding: 0.65rem 0.95rem;
  text-transform: uppercase;
}

.site-shell {
  display: grid;
  gap: clamp(1.2rem, 3vw, 3rem);
  grid-template-columns: minmax(14rem, 19rem) minmax(0, 1fr);
  margin: 0 auto;
  max-width: 96rem;
  padding: clamp(1rem, 3vw, 2.5rem);
}
.article-layout { grid-template-columns: minmax(14rem, 18rem) minmax(0, 1fr) minmax(12rem, 16rem); }
.content { min-width: 0; }
""".strip()


NAVIGATION_STYLES = """
.sidebar {
  align-self: start;
  background: var(--surface);
  border: 3px solid var(--ink);
  box-shadow: var(--shadow-hard);
  max-height: calc(100vh - 7rem);
  overflow: auto;
  padding: 1rem;
  position: sticky;
  top: 6.2rem;
}
.home-link, .navigation-section a {
  display: block;
  padding: 0.45rem 0.55rem;
  text-decoration: none;
}
.home-link {
  background: var(--ink);
  color: var(--surface);
  font-family: var(--font-mono);
  font-size: 0.82rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  margin-bottom: 1rem;
  text-transform: uppercase;
}
.navigation-section { border-top: 2px solid var(--ink); padding: 0.95rem 0 0.15rem; }
.navigation-section + .navigation-section { margin-top: 0.75rem; }
.navigation-section h2 {
  font-family: var(--font-display);
  font-size: 1.18rem;
  line-height: 1;
  margin-bottom: 0.55rem;
}
.navigation-section ol { counter-reset: nav-item; list-style: none; margin: 0; padding: 0; }
.navigation-section li { counter-increment: nav-item; }
.navigation-section li a {
  color: var(--ink-soft);
  display: grid;
  font-size: 0.92rem;
  gap: 0.5rem;
  grid-template-columns: 2ch 1fr;
}
.navigation-section li a::before {
  color: var(--signal);
  content: counter(nav-item, decimal-leading-zero);
  font-family: var(--font-mono);
  font-size: 0.72rem;
}
.navigation-section a[aria-current="page"], .home-link[aria-current="page"] {
  background: var(--taxi);
  color: var(--ink);
  font-weight: 700;
}
.article-toc {
  align-self: start;
  background: var(--surface);
  border: 3px solid var(--ink);
  box-shadow: var(--shadow-hard);
  max-height: calc(100vh - 7rem);
  overflow: auto;
  padding: 1rem;
  position: sticky;
  top: 6.2rem;
}
.article-toc ol { list-style: none; margin: 0.75rem 0 0; padding: 0; }
.article-toc li + li { margin-top: 0.45rem; }
.article-toc a {
  color: var(--ink-soft);
  display: block;
  font-size: 0.9rem;
  line-height: 1.35;
  text-decoration: none;
}
.article-toc a:hover { color: var(--signal); }
.article-toc__link--level-3 { padding-left: 0.85rem; }
""".strip()
