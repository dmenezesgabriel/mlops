const menuButton = document.querySelector('.menu-toggle');
const navigation = document.querySelector('#site-navigation');
const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');

if (menuButton instanceof HTMLButtonElement && navigation instanceof HTMLElement) {
  menuButton.addEventListener('click', () => {
    const expanded = menuButton.getAttribute('aria-expanded') === 'true';
    menuButton.setAttribute('aria-expanded', String(!expanded));
    navigation.classList.toggle('is-open', !expanded);
  });
}

// An absent data-theme means "auto": the CSS then tracks
// prefers-color-scheme on its own, so no media-query listener lives here.
const themeSelect = document.querySelector('.theme-select');

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

if (themeSelect instanceof HTMLSelectElement) {
  document.documentElement.classList.add('has-theme-select');
  const storedTheme = readStoredTheme();
  themeSelect.value =
    storedTheme === 'light' || storedTheme === 'dark' ? storedTheme : 'auto';
  themeSelect.addEventListener('change', () => {
    applyTheme(themeSelect.value);
    writeStoredTheme(themeSelect.value);
  });
}

if (!motionQuery.matches && 'IntersectionObserver' in window) {
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
}

const copyButtons = document.querySelectorAll('.code-copy-button');

if ('clipboard' in navigator && copyButtons.length) {
  document.documentElement.classList.add('has-code-copy');

  copyButtons.forEach((button) => {
    if (!(button instanceof HTMLButtonElement)) return;
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
  });
}

// The ssg:search-index meta carries the locale-root-relative index URL (same
// asset_prefix mechanism as site.css), so fetches and result hrefs stay
// inside the current locale from any page depth.
const searchRoot = document.querySelector('.site-search');
const searchInput = searchRoot?.querySelector('.search-input');
const searchResults = searchRoot?.querySelector('.search-results');
const searchNoResults = searchRoot?.querySelector('.search-no-results');
const searchIndexMeta = document.querySelector('meta[name="ssg:search-index"]');

if (
  searchRoot instanceof HTMLElement &&
  searchInput instanceof HTMLInputElement &&
  searchResults instanceof HTMLElement &&
  searchIndexMeta instanceof HTMLMetaElement &&
  'fetch' in window
) {
  document.documentElement.classList.add('has-search');

  const searchIndexUrl = new URL(searchIndexMeta.content, document.baseURI);
  let searchIndexPromise = null;

  const loadSearchIndex = () => {
    if (searchIndexPromise === null) {
      searchIndexPromise = fetch(searchIndexUrl)
        .then((response) => (response.ok ? response.json() : { docs: [] }))
        .then((index) => index.docs ?? [])
        .catch(() => []);
    }
    return searchIndexPromise;
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

  const closeSearchResults = () => {
    searchResults.hidden = true;
    searchInput.setAttribute('aria-expanded', 'false');
  };

  const renderSearchResults = (entries) => {
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

  const runSearch = () => {
    if (!searchInput.value.trim()) {
      closeSearchResults();
      return;
    }
    loadSearchIndex().then((docs) => {
      // Re-read the value inside .then: the index resolves async, so the
      // query may have advanced since this handler fired.
      const terms = normalizeSearchText(searchInput.value)
        .split(/\s+/)
        .filter(Boolean);
      if (!terms.length) {
        closeSearchResults();
        return;
      }
      renderSearchResults(rankSearchEntries(docs, terms));
    });
  };

  // Escape refocuses the input; that synthetic focus must not reopen the
  // dropdown the key just closed — hence the one-shot flag.
  let skipFocusSearch = false;
  searchInput.addEventListener('focus', () => {
    loadSearchIndex();
    if (skipFocusSearch) {
      skipFocusSearch = false;
      return;
    }
    runSearch();
  });
  searchInput.addEventListener('input', runSearch);

  searchRoot.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      closeSearchResults();
      skipFocusSearch = true;
      searchInput.focus();
      return;
    }
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
  });

  document.addEventListener('click', (event) => {
    if (
      event.target instanceof Node &&
      !searchRoot.contains(event.target)
    ) {
      closeSearchResults();
    }
  });
}

// TOC scrollspy: a heading crossing the pick band just under the sticky
// header marks its TOC link aria-current="true" (starlight
// components-internals/TableOfContents/starlight-toc.ts semantics).
// Starlight's 53px strip can be skipped by a fast scroll — it compensates
// by also observing every section sibling; observing only TOC headings
// needs a taller band (~top third of the viewport) instead.
const articleToc = document.querySelector('.article-toc');
const tocAnchors = articleToc
  ? Array.from(articleToc.querySelectorAll('a[href^="#"]'))
  : [];

if (articleToc && tocAnchors.length && 'IntersectionObserver' in window) {
  const siteHeader = document.querySelector('.site-header');
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

  const visibleHeadings = new Set();
  let currentTocLink = null;

  const setCurrentTocLink = (link) => {
    if (link === currentTocLink) return;
    if (currentTocLink) currentTocLink.removeAttribute('aria-current');
    link.setAttribute('aria-current', 'true');
    currentTocLink = link;
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

  const pickBandTop =
    Math.round(
      siteHeader ? siteHeader.getBoundingClientRect().height : 0
    ) + 16;
  const tocObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) {
          visibleHeadings.delete(entry.target);
          return;
        }
        visibleHeadings.add(entry.target);
      });
      // Document-order-last among visible headings is the section the
      // reader is in; when none is in the band the last mark stands.
      const current = tocHeadings
        .filter((heading) => visibleHeadings.has(heading))
        .pop();
      if (current) setCurrentTocLink(linkByHeading.get(current));
    },
    { rootMargin: `-${pickBandTop}px 0px -70% 0px` }
  );
  tocHeadings.forEach((heading) => tocObserver.observe(heading));
}

// Mobile TOC disclosure (starlight
// components/MobileTableOfContents.astro semantics): the <details> toggles
// natively without JS; these only close it again — after a link pick, on an
// outside click, and on Escape with focus handed back to the summary.
const mobileToc = document.querySelector('details.mobile-toc');

if (mobileToc instanceof HTMLDetailsElement) {
  mobileToc.querySelectorAll('a').forEach((anchor) => {
    anchor.addEventListener('click', () => {
      mobileToc.open = false;
    });
  });
  document.addEventListener('click', (event) => {
    if (event.target instanceof Node && !mobileToc.contains(event.target)) {
      mobileToc.open = false;
    }
  });
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape' || !mobileToc.open) return;
    const hadFocus = mobileToc.contains(document.activeElement);
    mobileToc.open = false;
    if (hadFocus) mobileToc.querySelector('summary')?.focus();
  });
}

// navigation.top parity (material components/top/index.ts): the button
// appears only when the reader scrolls up while below the top. It ships
// hidden in markup, so no-JS readers never see a dead control.
const backToTopButton = document.querySelector('.back-to-top');

if (backToTopButton instanceof HTMLButtonElement) {
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
  window.addEventListener('scroll', updateBackToTop, { passive: true });
  backToTopButton.addEventListener('click', () => {
    window.scrollTo({ top: 0 });
  });
}

if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
  const source = new EventSource('/__live_reload__');
  source.onmessage = (event) => {
    if (event.data === 'reload') {
      window.location.reload();
    }
  };
}
