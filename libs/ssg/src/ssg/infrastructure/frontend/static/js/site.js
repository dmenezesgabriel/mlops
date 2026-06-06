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

if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
  const source = new EventSource('/__live_reload__');
  source.onmessage = (event) => {
    if (event.data === 'reload') {
      window.location.reload();
    }
  };
}
