// Offline precache, emitted per locale variant at its root (the worker's
// scope). VERSION hashes every emitted file's path + bytes at build time,
// so changed output mints a fresh cache name and activation drops this
// scope's previous one; identical rebuilds keep it. Cache-first lookup is
// sound because a precached response is by construction the current
// deploy — misses fall back to the network, and a failed navigation
// degrades to the cached 404 rather than the browser's error page.
const VERSION = "{{ manifest.version }}";
const CACHE_PREFIX = `ssg-offline:${self.registration.scope}:`;
const CACHE = `${CACHE_PREFIX}${VERSION}`;
const PRECACHE_URLS = {{ manifest.urls | tojson }}.map(
  (path) => new URL(path, self.registration.scope).href
);
const NOT_FOUND_URL = new URL("404.html", self.registration.scope).href;
const cachePromise = caches.open(CACHE);

self.addEventListener("install", (event) => {
  event.waitUntil(
    cachePromise
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

// The prefix carries the scope so sibling-locale workers on one origin
// (e.g. / and /pt-BR/) never delete each other's caches.
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(
          names
            .filter((name) => name.startsWith(CACHE_PREFIX) && name !== CACHE)
            .map((name) => caches.delete(name))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  if (new URL(request.url).origin !== self.location.origin) return;
  event.respondWith(
    cachePromise.then(async (cache) => {
      const cached = await cache.match(request);
      if (cached) return cached;
      const response = await fetch(request).catch(() => null);
      if (response) return response;
      if (request.mode === "navigate") {
        const notFound = await cache.match(NOT_FOUND_URL);
        if (notFound) return notFound;
      }
      return Response.error();
    })
  );
});
