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

if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
  const source = new EventSource('/__live_reload__');
  source.onmessage = (event) => {
    if (event.data === 'reload') {
      window.location.reload();
    }
  };
}
