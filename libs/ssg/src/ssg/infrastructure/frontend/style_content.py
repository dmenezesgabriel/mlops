ARTICLE_STYLES = """
.hero, .article, .collection-card, .pager a {
  background: var(--surface);
  border: 3px solid var(--ink);
  box-shadow: var(--shadow-hard);
}
.hero {
  margin-bottom: clamp(1.2rem, 3vw, 2.5rem);
  overflow: hidden;
  padding: clamp(1.5rem, 5vw, 5rem);
  position: relative;
}
.hero::after {
  background: var(--taxi);
  border: 3px solid var(--ink);
  content: "DATA / STORY / OPS";
  font-family: var(--font-mono);
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.12em;
  padding: 0.45rem 0.8rem;
  position: absolute;
  right: clamp(1rem, 3vw, 2rem);
  top: clamp(1rem, 3vw, 2rem);
  transform: rotate(2deg);
}
.hero h1, .article h1 {
  font-family: var(--font-display);
  font-size: clamp(3rem, 9vw, 8rem);
  font-weight: 800;
  letter-spacing: -0.055em;
  line-height: 0.88;
  margin: 0.35rem 0 1rem;
  max-width: 11ch;
  overflow-wrap: break-word;
}
.article { overflow: clip; }
.article-header {
  background:
    linear-gradient(135deg, transparent 0 68%, rgb(242 189 34 / 0.42) 68% 100%),
    var(--surface);
  border-bottom: 3px solid var(--ink);
  padding: clamp(1.5rem, 5vw, 4rem);
}
.article-body { padding: clamp(1.2rem, 4vw, 3.5rem); }
.article-body > * { max-width: var(--measure); }
.article-body h2, .article-body h3 {
  font-family: var(--font-display);
  font-weight: 800;
  letter-spacing: -0.025em;
  line-height: 1;
  margin-top: clamp(2rem, 4vw, 3rem);
}
.article-body h2 { font-size: clamp(2rem, 4vw, 3.5rem); }
.article-body h3 { font-size: clamp(1.45rem, 3vw, 2.25rem); }
.article-body p, .article-body li { color: var(--ink-soft); }
.article-body blockquote {
  border-left: 0.55rem solid var(--signal);
  font-family: var(--font-display);
  font-size: clamp(1.4rem, 3vw, 2.2rem);
  line-height: 1.2;
  padding-left: 1rem;
}
.article-body table {
  border-collapse: collapse;
  display: block;
  max-width: 100%;
  overflow-x: auto;
}
.article-body th, .article-body td {
  border: 2px solid var(--ink);
  padding: 0.55rem 0.7rem;
  text-align: left;
}
.article-body th { background: var(--taxi); font-family: var(--font-mono); font-size: 0.82rem; }
""".strip()


MEDIA_STYLES = """
.source-panel, .media-frame, .notebook-cell, .data-callout, .chart-frame, .diagram-frame {
  background: var(--surface);
  border: 3px solid var(--ink);
  box-shadow: var(--shadow-hard);
  max-width: var(--wide-measure) !important;
}
.source-panel figcaption, .media-frame figcaption {
  align-items: center;
  border-bottom: 3px solid var(--ink);
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem 1rem;
  justify-content: space-between;
  padding: 0.7rem 0.9rem;
}
.source-panel__path {
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 0.8rem;
  overflow-wrap: anywhere;
}
.article-body pre, .notebook-input pre, .notebook-output pre, .source-panel pre {
  background:
    linear-gradient(90deg, rgb(255 255 255 / 0.035) 1px, transparent 1px),
    #17130f;
  background-size: 2.4rem 2.4rem;
  color: #f8ead0;
  font-family: var(--font-mono);
  font-size: 0.88rem;
  line-height: 1.62;
  margin: 0;
  max-width: 100%;
  overflow: auto;
  padding: 1rem;
}
.article-body code { font-family: var(--font-mono); }
.article-body :not(pre) > code {
  background: rgb(242 189 34 / 0.32);
  border: 1px solid var(--ink);
  padding: 0.08rem 0.25rem;
}
.media-frame video, .media-frame img, .notebook-image img,
.article-body > img, .article-body > video {
  background: var(--ink);
  height: auto;
  width: 100%;
}
.video-frame { background: var(--ink); }
.video-frame figcaption { background: var(--surface); }
.notebook-cell { overflow: hidden; }
.notebook-cell__header {
  align-items: center;
  background: var(--taxi);
  border-bottom: 3px solid var(--ink);
  display: flex;
  gap: 1rem;
  justify-content: space-between;
  padding: 0.65rem 0.9rem;
}
.notebook-cell__index, .notebook-output__label {
  font-family: var(--font-mono);
  font-size: 0.76rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
.notebook-output { border-top: 3px solid var(--ink); background: #211b15; color: #f8ead0; }
.notebook-output__label {
  background: var(--cyan);
  border-bottom: 3px solid var(--ink);
  color: var(--ink);
  display: block;
  padding: 0.45rem 0.8rem;
}
.notebook-output pre { background: transparent; }
.notebook-image { background: var(--surface); }
.data-callout, .chart-frame, .diagram-frame { padding: clamp(1rem, 3vw, 2rem); }
.data-callout { background: linear-gradient(135deg, rgb(45 168 160 / 0.18), var(--surface) 45%); }
""".strip()


COLLECTION_STYLES = """
.section-heading {
  border-bottom: 3px solid var(--ink);
  margin-bottom: 1rem;
  padding-bottom: 0.7rem;
}
.section-heading h2 {
  font-family: var(--font-display);
  font-size: clamp(2rem, 4vw, 3.5rem);
  line-height: 0.95;
}
.cards {
  display: grid;
  gap: clamp(1rem, 2vw, 1.5rem);
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 18rem), 1fr));
}
.collection-card { min-height: 19rem; padding: 1rem; position: relative; }
.collection-card::after {
  background: var(--signal);
  border: 3px solid var(--ink);
  content: "";
  height: 2.2rem;
  position: absolute;
  right: 1rem;
  top: -0.75rem;
  transform: rotate(5deg);
  width: 4.2rem;
}
.collection-card h3 {
  font-family: var(--font-display);
  font-size: clamp(1.8rem, 4vw, 3rem);
  line-height: 0.92;
  margin: 0.55rem 0 1.25rem;
}
.collection-card ol {
  border-top: 2px solid var(--ink);
  counter-reset: collection-page;
  list-style: none;
  margin: 0;
  padding: 0.75rem 0 0;
}
.collection-card li {
  counter-increment: collection-page;
  display: grid;
  gap: 0.65rem;
  grid-template-columns: 2ch 1fr;
}
.collection-card li + li { margin-top: 0.45rem; }
.collection-card li::before {
  color: var(--signal);
  content: counter(collection-page, decimal-leading-zero);
  font-family: var(--font-mono);
  font-size: 0.78rem;
  font-weight: 600;
}
.pager {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 15rem), 1fr));
  margin-top: 1.2rem;
}
.pager a { padding: 1rem; text-decoration: none; }
.pager span {
  color: var(--signal);
  display: block;
  font-family: var(--font-mono);
  font-size: 0.78rem;
}
.site-footer {
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 0.8rem;
  padding: 1rem clamp(1rem, 4vw, 3rem) 2rem;
  text-align: center;
}
""".strip()


RESPONSIVE_STYLES = """
@media (max-width: 58rem) {
  .site-header { grid-template-columns: auto 1fr auto; }
  .menu-toggle { display: inline-flex; }
  .site-shell { display: block; }
  .sidebar { display: none; margin: 1rem 0 1.4rem; max-height: none; position: static; }
  .sidebar.is-open { display: block; }
  .article-toc { margin-top: 1.4rem; max-height: none; position: static; }
  .hero::after { position: static; display: inline-block; margin-top: 1rem; }
}

@media (max-width: 40rem) {
  .site-header { gap: 0.65rem; padding: 0.7rem 0.85rem; }
  .masthead-mark { min-height: 2.8rem; padding: 0 0.6rem; }
  .site-description { display: none; }
  .hero h1, .article h1 { font-size: clamp(2.3rem, 13.5vw, 3.7rem); }
  .article-body { padding: 1rem; }
  .source-panel, .media-frame, .notebook-cell { box-shadow: 0.35rem 0.35rem 0 var(--ink); }
}
""".strip()


MOTION_STYLES = """
@media (prefers-reduced-motion: no-preference) {
  .skip-link, a, button {
    transition: color var(--speed), background-color var(--speed), transform var(--speed);
  }
  .collection-card:hover, .pager a:hover { transform: translate(-0.18rem, -0.18rem); }
  .has-reveal .story-step, .has-reveal .media-frame, .has-reveal .notebook-cell {
    transform: translateY(1.1rem);
    transition: transform 520ms ease;
  }
  .has-reveal .story-step.is-visible,
  .has-reveal .media-frame.is-visible,
  .has-reveal .notebook-cell.is-visible {
    transform: translateY(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
    transition-duration: 0.01ms !important;
  }
}
""".strip()
