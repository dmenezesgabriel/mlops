// Sitemap-gated instant navigation (material integrations/instant parity):
// internal links are fetched and swapped in place; external URLs,
// cross-locale links, anchors and modified clicks navigate natively, and
// any fetch failure falls back to a full reload. site.js re-runs its
// per-page feature mounts on the 'ssg:navigated' announcement below.

const SWAP_SELECTORS = [
  'header.site-header',
  '.site-shell',
  'footer.site-footer',
  '.back-to-top',
];

// Sitemap locs and resolved hrefs disagree about the trailing slash and
// the directory index (`absolute_url('')` carries neither, a resolved home
// link ends in `/index.html`); compare on origin+path with both stripped.
const canonicalUrl = (url) => {
  const path = url.pathname
    .replace(/\/index\.html$/, '')
    .replace(/\/$/, '');
  return `${url.origin}${path}`;
};

// Sitemap locs are absolute under site.url, which may sit below a path
// prefix the preview server does not serve (site.yaml uses /mlops, the
// local server mounts the variant root at /). The template always emits
// the variant root loc first (sitemap.xml), so every loc is relativized
// against it and re-resolved inside the sitemap's own serving directory —
// production-absolute entries then match localhost previews too, which is
// what material's resolve() host rewrite achieves for its flat layout.
const extractSitemapPaths = (xml, sitemapUrl) => {
  const sitemapDocument = new DOMParser().parseFromString(xml, 'text/xml');
  if (sitemapDocument.querySelector('parsererror')) return new Set();
  const locs = sitemapDocument.querySelectorAll('url > loc');
  if (!locs.length) return new Set();
  const rootLoc = new URL(locs[0].textContent ?? '', sitemapUrl);
  const rootPath = rootLoc.pathname.endsWith('/')
    ? rootLoc.pathname
    : `${rootLoc.pathname}/`;
  const sitemapDir = new URL('.', sitemapUrl);
  const paths = new Set();
  locs.forEach((loc) => {
    const locUrl = new URL(loc.textContent ?? '', sitemapUrl);
    if (!locUrl.pathname.startsWith(rootPath)) return;
    paths.add(
      canonicalUrl(new URL(locUrl.pathname.slice(rootPath.length), sitemapDir))
    );
  });
  return paths;
};

const resolveRelativeUrls = (doc, baseUrl) => {
  doc.querySelectorAll('[href], [src]').forEach((element) => {
    for (const key of ['href', 'src']) {
      const value = element.getAttribute(key);
      // Keep fragment-only refs as `#…`: resolving them is semantically
      // identical but breaks the `a[href^='#']` collections the remounting
      // features (scrollspy, mobile TOC) run on swapped-in markup.
      if (
        value &&
        !value.startsWith('#') &&
        !/^(?:[a-z]+:)?\/\//i.test(value)
      ) {
        element.setAttribute(key, new URL(value, baseUrl).href);
        break;
      }
    }
  });
};

const headTags = (doc) => {
  const tags = new Map();
  for (const element of doc.head.children) tags.set(element.outerHTML, element);
  return tags;
};

// Head diff (material instant/index.ts head() parity): identical tags are
// kept untouched — that is what keeps the site.js/CDN script tags from
// ever re-executing; new tags append, stale tags drop.
const mergeHead = (nextDocument) => {
  const staleTags = headTags(document);
  for (const [html, element] of headTags(nextDocument)) {
    if (staleTags.has(html)) {
      staleTags.delete(html);
      continue;
    }
    document.head.appendChild(element);
  }
  for (const element of staleTags.values()) element.remove();
};

const swapBodyRegions = (nextDocument) => {
  for (const selector of SWAP_SELECTORS) {
    const current = document.querySelector(selector);
    const next = nextDocument.querySelector(selector);
    if (current && next) current.replaceWith(next);
  }
};

const restoreScroll = (url, savedState) => {
  const target = url.hash
    ? document.getElementById(decodeURIComponent(url.hash.slice(1)))
    : null;
  if (target) {
    target.scrollIntoView({ behavior: 'instant', block: 'start' });
    return;
  }
  window.scrollTo({ top: savedState?.y ?? 0, behavior: 'instant' });
};

// The widget embedder (embed-amd.js) renders widget-view scripts once at
// page load; swapped-in widget DOM needs an explicit re-render.
const remountWidgetViews = () => {
  const widgetScript = document.querySelector(
    'script[type^="application/vnd.jupyter.widget"]'
  );
  if (!widgetScript) return;
  window.require?.(
    ['@jupyter-widgets/html-manager/dist/libembed-amd'],
    (manager) => {
      if (typeof manager.renderWidgets === 'function') manager.renderWidgets();
    }
  );
};

const settleAfterSwap = (url, savedState) => {
  document.dispatchEvent(new CustomEvent('ssg:navigated'));
  remountWidgetViews();
  document.getElementById('main-content')?.focus({ preventScroll: true });
  restoreScroll(url, savedState);
};

const swapInFetchedDocument = (html, url) => {
  const nextDocument = new DOMParser().parseFromString(html, 'text/html');
  resolveRelativeUrls(nextDocument, url);
  swapBodyRegions(nextDocument);
  mergeHead(nextDocument);
};

const navigateTo = (state, url, savedState) => {
  state.fetchController?.abort();
  const controller = new AbortController();
  state.fetchController = controller;
  fetch(url.href, { signal: controller.signal })
    .then((response) => {
      if (!response.ok) {
        throw new Error(
          `Instant navigation fetch failed: ${response.status} for ${url.href}`
        );
      }
      return response.text();
    })
    .then((html) => swapInFetchedDocument(html, url))
    .then(() => {
      if (state.fetchController !== controller) return;
      settleAfterSwap(url, savedState);
    })
    .catch(() => {
      // A newer navigation aborted this fetch; it owns the outcome now.
      if (controller.signal.aborted) return;
      window.location.assign(url.href);
    });
};

const interceptableUrl = (state, event) => {
  if (!(event.target instanceof Element)) return null;
  const anchor = event.target.closest('a');
  if (!anchor || anchor.target || anchor.hasAttribute('download')) return null;
  const url = new URL(anchor.href, document.baseURI);
  if (url.origin !== window.location.origin) return null;
  if (!state.sitemapPaths?.has(canonicalUrl(url))) return null;
  return url;
};

const interceptClicks = (state) => {
  document.body.addEventListener('click', (event) => {
    if (
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return;
    }
    const url = interceptableUrl(state, event);
    if (!url || url.pathname === state.currentPathname) return;
    event.preventDefault();
    state.currentPathname = url.pathname;
    history.replaceState({ y: window.scrollY }, '');
    history.pushState(null, '', url.href);
    navigateTo(state, url, null);
  });
};

const interceptPopstate = (state) => {
  window.addEventListener('popstate', (event) => {
    const url = new URL(window.location.href);
    const samePage = url.pathname === state.currentPathname;
    state.currentPathname = url.pathname;
    if (samePage) {
      restoreScroll(url, event.state);
      return;
    }
    navigateTo(state, url, event.state);
  });
};

// Material tracks the viewport offset debounced (instant/index.ts:426-432)
// so back/forward restores the reader's position, not the page top.
const trackScrollOffset = () => {
  let saveTimer = 0;
  window.addEventListener(
    'scroll',
    () => {
      clearTimeout(saveTimer);
      saveTimer = setTimeout(() => {
        history.replaceState({ y: window.scrollY }, '');
      }, 100);
    },
    { passive: true }
  );
};

const injectPrefetchLink = (state, href) => {
  const link = document.createElement('link');
  link.rel = 'prefetch';
  link.href = href;
  link.onload = () => link.remove();
  link.onerror = () => link.remove();
  document.head.appendChild(link);
  state.prefetched.add(new URL(href).pathname);
};

// Prefetch on hover/focus intent (material instant/index.ts:434-467
// parity): debounce 25ms, dedupe per path, drop the link tag once loaded.
const wirePrefetch = (state) => {
  let prefetchTimer = 0;
  const schedulePrefetch = (event) => {
    const url = interceptableUrl(state, event);
    if (
      !url ||
      url.pathname === state.currentPathname ||
      state.prefetched.has(url.pathname)
    ) {
      return;
    }
    clearTimeout(prefetchTimer);
    prefetchTimer = setTimeout(() => injectPrefetchLink(state, url.href), 25);
  };
  document.body.addEventListener('mouseover', schedulePrefetch);
  document.body.addEventListener('focusin', schedulePrefetch);
};

const loadSitemap = (state, sitemapUrl) => {
  fetch(sitemapUrl)
    .then((response) => (response.ok ? response.text() : ''))
    .then((xml) => extractSitemapPaths(xml, sitemapUrl))
    .then((paths) => {
      state.sitemapPaths = paths;
    })
    .catch(() => {
      state.sitemapPaths = new Set();
    });
};

const activateInstantNavigation = (sitemapUrl) => {
  const state = {
    sitemapPaths: null,
    fetchController: null,
    prefetched: new Set(),
    currentPathname: window.location.pathname,
  };
  // Relative hrefs resolve against the serving origin up front so the head
  // diff below compares like with like across page depths (material
  // instant/index.ts resolve() parity).
  resolveRelativeUrls(document, window.location.href);
  loadSitemap(state, sitemapUrl);
  interceptClicks(state);
  interceptPopstate(state);
  trackScrollOffset();
  wirePrefetch(state);
  history.scrollRestoration = 'manual';
  window.addEventListener('beforeunload', () => {
    history.scrollRestoration = 'auto';
  });
};

const sitemapMeta = document.querySelector('meta[name="ssg:sitemap"]');
const sitemapUrl =
  sitemapMeta instanceof HTMLMetaElement
    ? new URL(sitemapMeta.content, document.baseURI)
    : null;

if (sitemapUrl && window.location.protocol !== 'file:') {
  activateInstantNavigation(sitemapUrl);
}
