// Build-time Mermaid → SVG renderer for the ssg-mermaid plugin.
//
// svgdom supplies the layout-capable DOM mermaid measures against
// (getBBox/getComputedTextLength — plain jsdom lacks text metrics and
// collapses flowchart layout); jsdom only hosts dompurify and the few
// globals svgdom does not implement. This is the DOM wiring
// isomorphic-mermaid@0.1.1 (MIT, dist/main.js) proved, vendored here so
// this package pins its own dependency set.
import { readFileSync } from "node:fs";
import createDOMPurify from "dompurify";
import { JSDOM } from "jsdom";
import { createHTMLWindow } from "svgdom";

const jsdomWindow = new JSDOM("").window;
const DOMPurify = createDOMPurify(jsdomWindow);
// mermaid imports the `dompurify` module's default export (the factory);
// assigning the configured instance's methods onto it routes sanitize()
// through the jsdom window above.
Object.assign(createDOMPurify, DOMPurify);

const svgWindow = createHTMLWindow();
Object.assign(globalThis, {
  window: svgWindow,
  document: svgWindow.document,
});

// mermaid's render path reaches bare globals (CSSStyleSheet for themeCSS
// adoption, DOMParser/XMLSerializer for label plumbing) that svgdom does
// not implement — seed them from jsdom where missing.
for (const name of [
  "CSSStyleSheet",
  "Document",
  "Node",
  "Element",
  "DOMParser",
  "XMLSerializer",
  "getComputedStyle",
]) {
  if (!(name in globalThis)) {
    Object.defineProperty(globalThis, name, {
      value: jsdomWindow[name],
      configurable: true,
    });
  }
}

// Dynamic import: mermaid's module evaluation must observe the DOM
// globals above; a static import would run before they exist.
const mermaid = (await import("mermaid")).default;

// Unscoped selectors on purpose: mermaid prefixes themeCSS with the
// diagram id itself, keeping rules local to this svg. The var() refs
// resolve against the built page's palette (light-dark() via the site's
// color-scheme), so diagrams follow the theme switch with no re-render.
const THEME_CSS = `
.node rect,.node circle,.node ellipse,.node polygon,.node path{fill:var(--surface);stroke:var(--ink)}
.edgePath .path,.flowchart-link,.messageLine0,.messageLine1,.loopLine,.transition,.relationshipLine{stroke:var(--ink)}
marker,marker path{fill:var(--ink);stroke:var(--ink)}
.edgeLabel,.edgeLabel p,.label,.label text,.nodeLabel,.messageText,.noteText,.loopText,.actor,text,span{fill:var(--ink);color:var(--ink)}
.cluster rect{fill:var(--surface-muted);stroke:var(--ink-soft)}
.actor,.note,.edgeLabel rect{fill:var(--surface);stroke:var(--ink)}
`;

mermaid.initialize({
  startOnLoad: false,
  securityLevel: "strict",
  htmlLabels: false,
  flowchart: { htmlLabels: false },
  fontFamily: "inherit",
  themeCSS: THEME_CSS,
});

const request = JSON.parse(readFileSync(0, "utf8"));
try {
  const { svg } = await mermaid.render("ssg-mermaid-0", request.source);
  process.stdout.write(JSON.stringify({ svg }));
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  process.stdout.write(JSON.stringify({ error: message }));
}
