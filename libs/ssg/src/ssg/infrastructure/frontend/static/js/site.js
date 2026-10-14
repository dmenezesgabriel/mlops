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

if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
  const source = new EventSource('/__live_reload__');
  source.onmessage = (event) => {
    if (event.data === 'reload') {
      window.location.reload();
    }
  };
}
