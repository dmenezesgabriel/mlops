// Per-page feature mounts. instant.js swaps page regions in place and
// announces 'ssg:navigated'; every mount below re-runs on that event, and
// listeners living on document/window take the per-page AbortSignal so a
// swap retires the previous page's handlers with it.

const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');

const readStoredTheme = () => {
  try {
    return window.localStorage.getItem('ssg-theme');
  } catch (error) {
    return null;
  }
};

const writeStoredTheme = (value) => {
  try {
    if (value === 'auto') {
      window.localStorage.removeItem('ssg-theme');
      return;
    }
    window.localStorage.setItem('ssg-theme', value);
  } catch (error) {
    // Storage can be blocked (private mode); the pick still applies to
    // this session, it just does not survive a reload.
  }
};

const applyTheme = (value) => {
  if (value === 'auto') {
    document.body.removeAttribute('data-theme');
    return;
  }
  document.body.dataset.theme = value;
};

const mountMenuToggle = () => {
  const menuButton = document.querySelector('.menu-toggle');
  const navigation = document.querySelector('#site-navigation');
  if (
    !(menuButton instanceof HTMLButtonElement) ||
    !(navigation instanceof HTMLElement)
  ) {
    return;
  }
  menuButton.addEventListener('click', () => {
    const expanded = menuButton.getAttribute('aria-expanded') === 'true';
    menuButton.setAttribute('aria-expanded', String(!expanded));
    navigation.classList.toggle('is-open', !expanded);
  });
};

// An absent data-theme means "auto": the CSS then tracks
// prefers-color-scheme on its own, so no media-query listener lives here.
const mountThemeSelect = () => {
  const themeSelect = document.querySelector('.theme-select');
  if (!(themeSelect instanceof HTMLSelectElement)) return;
  document.documentElement.classList.add('has-theme-select');
  const storedTheme = readStoredTheme();
  themeSelect.value =
    storedTheme === 'light' || storedTheme === 'dark' ? storedTheme : 'auto';
  themeSelect.addEventListener('change', () => {
    applyTheme(themeSelect.value);
    writeStoredTheme(themeSelect.value);
  });
};

const mountRevealAnimation = () => {
  if (motionQuery.matches || !('IntersectionObserver' in window)) return;
  document.documentElement.classList.add('has-reveal');

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('is-visible');
      observer.unobserve(entry.target);
    });
  }, { rootMargin: '0px 0px -12% 0px', threshold: 0.12 });

  document
    .querySelectorAll('.story-step, .media-frame, .notebook-cell')
    .forEach((element) => observer.observe(element));
};

const wireCodeCopyButton = (button) => {
  let revertTimer = 0;
  button.addEventListener('click', () => {
    const source = button.closest('.code-frame')?.querySelector('pre > code');
    const text = source?.textContent?.trimEnd() ?? '';
    if (!text) return;

    navigator.clipboard.writeText(text).then(() => {
      button.textContent = button.dataset.copiedLabel ?? '';
      button.classList.add('is-copied');
      clearTimeout(revertTimer);
      revertTimer = setTimeout(() => {
        button.textContent = '';
        button.classList.remove('is-copied');
      }, 2000);
    }, () => {});
  });
};

const mountCodeCopyButtons = () => {
  const copyButtons = document.querySelectorAll('.code-copy-button');
  if (!('clipboard' in navigator) || !copyButtons.length) return;
  document.documentElement.classList.add('has-code-copy');
  copyButtons.forEach((button) => {
    if (button instanceof HTMLButtonElement) wireCodeCopyButton(button);
  });
};

// The locale search index is identical from any page depth; the fetch
// promise lives in this script-scope cache so instant-navigation swaps
// reuse it. A failed fetch evicts its entry so a later mount retries
// instead of caching the failure forever.
const searchIndexCache = new Map();

const loadSearchIndex = (indexUrl) => {
  const cachedPromise = searchIndexCache.get(indexUrl.href);
  if (cachedPromise) return cachedPromise;
  const indexPromise = fetch(indexUrl)
    .then((response) => (response.ok ? response.json() : { docs: [] }))
    .then((index) => index.docs ?? [])
    .catch(() => {
      searchIndexCache.delete(indexUrl.href);
      return [];
    });
  searchIndexCache.set(indexUrl.href, indexPromise);
  return indexPromise;
};

const normalizeSearchText = (value) =>
  value.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();

// AND-match: every query term must hit title or text; a title hit weighs
// ten text hits so a page named after the term outranks mere mentions.
const scoreSearchEntry = (entry, terms) => {
  const title = normalizeSearchText(entry.title ?? '');
  const text = normalizeSearchText(entry.text ?? '');
  let score = 0;
  for (const term of terms) {
    const titleHits = title.split(term).length - 1;
    const textHits = text.split(term).length - 1;
    if (titleHits + textHits === 0) return -1;
    score += titleHits * 10 + textHits;
  }
  return score;
};

const rankSearchEntries = (docs, terms) =>
  docs
    .map((entry) => ({ entry, score: scoreSearchEntry(entry, terms) }))
    .filter((result) => result.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 10)
    .map((result) => result.entry);

const closeSearchResults = (searchInput, searchResults) => {
  searchResults.hidden = true;
  searchInput.setAttribute('aria-expanded', 'false');
};

const renderSearchResults = (context, entries) => {
  const { searchInput, searchResults, searchNoResults, searchIndexUrl } =
    context;
  searchResults
    .querySelectorAll('li:not(.search-no-results)')
    .forEach((item) => item.remove());
  entries.forEach((entry) => {
    const item = document.createElement('li');
    item.setAttribute('role', 'option');
    const link = document.createElement('a');
    link.className = 'search-result-link';
    link.href = new URL(entry.location, searchIndexUrl).href;
    link.textContent = entry.title;
    item.appendChild(link);
    searchResults.appendChild(item);
  });
  if (searchNoResults instanceof HTMLElement) {
    searchNoResults.hidden = entries.length > 0;
  }
  searchResults.hidden = false;
  searchInput.setAttribute('aria-expanded', 'true');
};

const runSearch = (context) => {
  const { searchInput, searchResults } = context;
  if (!searchInput.value.trim()) {
    closeSearchResults(searchInput, searchResults);
    return;
  }
  loadSearchIndex(context.searchIndexUrl).then((docs) => {
    // Re-read the value inside .then: the index resolves async, so the
    // query may have advanced since this handler fired.
    const terms = normalizeSearchText(searchInput.value)
      .split(/\s+/)
      .filter(Boolean);
    if (!terms.length) {
      closeSearchResults(searchInput, searchResults);
      return;
    }
    renderSearchResults(context, rankSearchEntries(docs, terms));
  });
};

const handleSearchKeydown = (event, searchResults) => {
  if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
  const links = Array.from(
    searchResults.querySelectorAll('a.search-result-link')
  );
  if (searchResults.hidden || !links.length) return;
  event.preventDefault();
  const current = links.indexOf(document.activeElement);
  const next =
    event.key === 'ArrowDown'
      ? (current + 1) % links.length
      : (current <= 0 ? links.length : current) - 1;
  links[next].focus();
};

const handleSearchEscape = (searchInput, searchResults, consumeNextFocus) => {
  closeSearchResults(searchInput, searchResults);
  consumeNextFocus();
  searchInput.focus();
};

const findSearchElements = () => {
  const searchRoot = document.querySelector('.site-search');
  return {
    searchRoot,
    searchInput: searchRoot?.querySelector('.search-input'),
    searchResults: searchRoot?.querySelector('.search-results'),
    searchNoResults: searchRoot?.querySelector('.search-no-results'),
    searchIndexMeta: document.querySelector('meta[name="ssg:search-index"]'),
  };
};

const wireSearchInputAndKeys = (context) => {
  const { searchRoot, searchInput, searchResults } = context;
  const run = () => runSearch(context);
  // Escape refocuses the input; that synthetic focus must not reopen the
  // dropdown the key just closed — hence the one-shot flag.
  let skipFocusSearch = false;
  searchInput.addEventListener('focus', () => {
    loadSearchIndex(context.searchIndexUrl);
    if (skipFocusSearch) {
      skipFocusSearch = false;
      return;
    }
    run();
  });
  searchInput.addEventListener('input', run);
  searchRoot.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      handleSearchEscape(searchInput, searchResults, () => {
        skipFocusSearch = true;
      });
      return;
    }
    handleSearchKeydown(event, searchResults);
  });
};

const wireSearchOutsideClose = (signal, context) => {
  const { searchRoot, searchInput, searchResults } = context;
  document.addEventListener(
    'click',
    (event) => {
      if (event.target instanceof Node && !searchRoot.contains(event.target)) {
        closeSearchResults(searchInput, searchResults);
      }
    },
    { signal }
  );
};

const mountSearch = (signal) => {
  const context = findSearchElements();
  const ready =
    context.searchRoot instanceof HTMLElement &&
    context.searchInput instanceof HTMLInputElement &&
    context.searchResults instanceof HTMLElement &&
    context.searchIndexMeta instanceof HTMLMetaElement &&
    'fetch' in window;
  if (!ready) return;
  document.documentElement.classList.add('has-search');
  context.searchIndexUrl = new URL(
    context.searchIndexMeta.content,
    document.baseURI
  );
  wireSearchInputAndKeys(context);
  wireSearchOutsideClose(signal, context);
};

// TOC scrollspy: a heading crossing the pick band just under the sticky
// header marks its TOC link aria-current="true" (starlight
// components-internals/TableOfContents/starlight-toc.ts semantics).
// Starlight's 53px strip can be skipped by a fast scroll — it compensates
// by also observing every section sibling; observing only TOC headings
// needs a taller band (~top third of the viewport) instead.
const collectTocHeadings = (tocAnchors) => {
  const linkByHeading = new Map();
  const tocHeadings = [];
  tocAnchors.forEach((anchor) => {
    const heading = document.getElementById(
      decodeURIComponent(anchor.hash.slice(1))
    );
    if (heading) {
      linkByHeading.set(heading, anchor);
      tocHeadings.push(heading);
    }
  });
  return { linkByHeading, tocHeadings };
};

const markCurrentTocLink = (articleToc, spyState, link) => {
  if (link === spyState.currentLink) return;
  if (spyState.currentLink) spyState.currentLink.removeAttribute('aria-current');
  link.setAttribute('aria-current', 'true');
  spyState.currentLink = link;
  // toc.follow parity: keep the active anchor visible inside the
  // self-scrolling aside — scrollTop touches the aside only, so the page
  // position never moves.
  if (
    link.offsetTop < articleToc.scrollTop ||
    link.offsetTop + link.offsetHeight >
      articleToc.scrollTop + articleToc.clientHeight
  ) {
    articleToc.scrollTop = link.offsetTop - articleToc.clientHeight / 2;
  }
};

const updateTocSpy = (articleToc, spyState, linkByHeading, tocHeadings, entries) => {
  entries.forEach((entry) => {
    if (!entry.isIntersecting) {
      spyState.visibleHeadings.delete(entry.target);
      return;
    }
    spyState.visibleHeadings.add(entry.target);
  });
  // Document-order-last among visible headings is the section the
  // reader is in; when none is in the band the last mark stands.
  const current = tocHeadings
    .filter((heading) => spyState.visibleHeadings.has(heading))
    .pop();
  if (current) markCurrentTocLink(articleToc, spyState, linkByHeading.get(current));
};

const observeTocHeadings = (articleToc, siteHeader, linkByHeading, tocHeadings) => {
  const spyState = { visibleHeadings: new Set(), currentLink: null };
  const pickBandTop =
    Math.round(siteHeader ? siteHeader.getBoundingClientRect().height : 0) + 16;
  const tocObserver = new IntersectionObserver(
    (entries) =>
      updateTocSpy(articleToc, spyState, linkByHeading, tocHeadings, entries),
    { rootMargin: `-${pickBandTop}px 0px -70% 0px` }
  );
  tocHeadings.forEach((heading) => tocObserver.observe(heading));
};

const mountArticleScrollSpy = () => {
  const articleToc = document.querySelector('.article-toc');
  const tocAnchors = articleToc
    ? Array.from(articleToc.querySelectorAll('a[href^="#"]'))
    : [];
  if (!articleToc || !tocAnchors.length || !('IntersectionObserver' in window)) {
    return;
  }
  const { linkByHeading, tocHeadings } = collectTocHeadings(tocAnchors);
  if (!tocHeadings.length) return;
  observeTocHeadings(
    articleToc,
    document.querySelector('.site-header'),
    linkByHeading,
    tocHeadings
  );
};

// Mobile TOC disclosure (starlight
// components/MobileTableOfContents.astro semantics): the <details> toggles
// natively without JS; these only close it again — after a link pick, on an
// outside click, and on Escape with focus handed back to the summary.
const mountMobileToc = (signal) => {
  const mobileToc = document.querySelector('details.mobile-toc');
  if (!(mobileToc instanceof HTMLDetailsElement)) return;
  mobileToc.querySelectorAll('a').forEach((anchor) => {
    anchor.addEventListener('click', () => {
      mobileToc.open = false;
    });
  });
  document.addEventListener(
    'click',
    (event) => {
      if (event.target instanceof Node && !mobileToc.contains(event.target)) {
        mobileToc.open = false;
      }
    },
    { signal }
  );
  document.addEventListener(
    'keydown',
    (event) => {
      if (event.key !== 'Escape' || !mobileToc.open) return;
      const hadFocus = mobileToc.contains(document.activeElement);
      mobileToc.open = false;
      if (hadFocus) mobileToc.querySelector('summary')?.focus();
    },
    { signal }
  );
};

// navigation.top parity (material components/top/index.ts): the button
// appears only when the reader scrolls up while below the top. It ships
// hidden in markup, so no-JS readers never see a dead control.
const mountBackToTop = (signal) => {
  const backToTopButton = document.querySelector('.back-to-top');
  if (!(backToTopButton instanceof HTMLButtonElement)) return;
  const siteHeader = document.querySelector('.site-header');
  let lastScrollY = window.scrollY;
  const updateBackToTop = () => {
    const scrollY = window.scrollY;
    backToTopButton.hidden = !(scrollY > 0 && scrollY < lastScrollY);
    if (!backToTopButton.hidden && siteHeader) {
      backToTopButton.style.top = `${
        siteHeader.getBoundingClientRect().height + 16
      }px`;
    }
    lastScrollY = scrollY;
  };
  window.addEventListener('scroll', updateBackToTop, {
    passive: true,
    signal,
  });
  backToTopButton.addEventListener('click', () => {
    window.scrollTo({ top: 0 });
  });
};

// Version switcher (mike/material version-selector parity): the static
// hrefs already reach every version's same-locale root without JS; this
// adds (a) a versions.json refresh so pages from older builds list newer
// versions, and (b) same-page switching — the current path inside the
// version tree (query + hash kept) is probed on the target version and
// used when it exists, falling back to the version root like material's
// selectedVersionCorrespondingURL.
const mountVersionSwitcher = () => {
  const switcher = document.querySelector('[data-version-switcher]');
  const currentAnchor = switcher?.querySelector('a[aria-current]');
  if (
    !(switcher instanceof HTMLDetailsElement) ||
    !(currentAnchor instanceof HTMLAnchorElement) ||
    !('fetch' in window)
  ) {
    return;
  }
  const localePrefix = switcher.dataset.localePrefix ?? '';
  // The current link's dir part is this page's locale root; the version
  // root sits one level higher when the locale is nested.
  const linkDir = (currentAnchor.getAttribute('href') ?? '').replace(
    /index\.html$/,
    ''
  );
  const versionRoot = new URL(
    `${linkDir}${localePrefix ? '../' : ''}`,
    window.location.href
  );
  const restWithinVersion = () =>
    window.location.pathname.slice(versionRoot.pathname.length);
  switcher.addEventListener('click', (event) => {
    if (
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return;
    }
    const anchor =
      event.target instanceof Element
        ? event.target.closest('a[data-version-segment]')
        : null;
    if (!(anchor instanceof HTMLAnchorElement)) return;
    const target = anchor.dataset.versionSegment;
    if (!target) return;
    event.preventDefault();
    const candidate = new URL(
      `../${target}/${restWithinVersion()}${window.location.search}${window.location.hash}`,
      versionRoot
    );
    fetch(candidate.href)
      .then((response) => {
        window.location.assign(response.ok ? candidate.href : anchor.href);
      })
      .catch(() => window.location.assign(anchor.href));
  });
  fetch(new URL('../versions.json', versionRoot))
    .then((response) => (response.ok ? response.json() : null))
    .then((entries) => {
      if (!Array.isArray(entries)) return;
      const list = switcher.querySelector('ul');
      if (!list) return;
      const currentSegment = decodeURIComponent(
        versionRoot.pathname.replace(/\/$/, '').split('/').pop() ?? ''
      );
      list.textContent = '';
      entries
        .filter(
          (entry) =>
            entry &&
            typeof entry.version === 'string' &&
            !entry.properties?.hidden
        )
        .forEach((entry) => {
          const anchor = document.createElement('a');
          anchor.href = new URL(
            `../${entry.version}/${localePrefix}index.html`,
            versionRoot
          ).href;
          anchor.dataset.versionSegment = entry.version;
          if (
            entry.version === currentSegment ||
            (entry.aliases ?? []).includes(currentSegment)
          ) {
            anchor.setAttribute('aria-current', 'page');
          }
          anchor.textContent = entry.title ?? entry.version;
          const firstAlias = (entry.aliases ?? [])[0];
          if (firstAlias) {
            const badge = document.createElement('span');
            badge.className = 'version-switcher__alias';
            badge.textContent = firstAlias;
            anchor.append(' ', badge);
          }
          const item = document.createElement('li');
          item.appendChild(anchor);
          list.appendChild(item);
        });
    })
    .catch(() => {
      // No registry or a network hiccup — the static list stays usable.
    });
};

const mountLiveReload = () => {
  if (
    window.location.hostname !== 'localhost' &&
    window.location.hostname !== '127.0.0.1'
  ) {
    return;
  }
  const source = new EventSource('/__live_reload__');
  source.onmessage = (event) => {
    if (event.data === 'reload') {
      window.location.reload();
    }
  };
};

// Offline precache: every variant root ships a sw.js scoped to its locale
// tree. Registration is once per page load (identical re-registrations are
// no-ops); the API is absent on file:// and insecure origins, and the
// origin guard skips it when an absolute meta points at the deployed
// origin while previewing locally — the same posture instant.js takes.
const mountServiceWorker = () => {
  const meta = document.querySelector('meta[name="ssg:service-worker"]');
  if (
    !('serviceWorker' in navigator) ||
    !(meta instanceof HTMLMetaElement)
  ) {
    return;
  }
  const workerUrl = new URL(meta.content, document.baseURI);
  if (workerUrl.origin !== window.location.origin) return;
  navigator.serviceWorker.register(workerUrl).catch(() => {});
};

const mountPageFeatures = (signal) => {
  mountMenuToggle();
  mountThemeSelect();
  mountRevealAnimation();
  mountCodeCopyButtons();
  mountSearch(signal);
  mountArticleScrollSpy();
  mountMobileToc(signal);
  mountVersionSwitcher();
  mountBackToTop(signal);
};

let pageListenerController = new AbortController();

const remountPageFeatures = () => {
  pageListenerController.abort();
  pageListenerController = new AbortController();
  mountPageFeatures(pageListenerController.signal);
};

remountPageFeatures();
mountLiveReload();
mountServiceWorker();
// instant.js announces every content swap; the mounts re-run so search,
// theme and scrollspy bind to the freshly swapped regions.
document.addEventListener('ssg:navigated', remountPageFeatures);
