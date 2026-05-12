/* Wyltek Studio service worker.
   Bumping CACHE_VERSION invalidates the precache on next activate. */
const CACHE_VERSION = 'wyltek-v17';
const PRECACHE_URLS = [
  '/',
  '/static/css/style.css',
  '/static/css/nav.css',
  '/static/js/nav.js',
  '/static/js/project-picker.js',
  '/static/images/logo-icon.png',
  '/static/images/logo-192.png',
  '/static/images/logo-512.png',
  '/manifest.json'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) =>
      cache.addAll(PRECACHE_URLS).catch(() => {
        // best-effort: don't block install on a single missing asset
      })
    ).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // Never cache the dynamic API surface or websocket upgrades.
  if (url.pathname.startsWith('/api/')
      || url.pathname.startsWith('/ws')
      || url.pathname.startsWith('/outputs/')) {
    return;
  }

  // Static assets — cache-first.
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((res) => {
        if (res && res.status === 200) {
          const copy = res.clone();
          caches.open(CACHE_VERSION).then((c) => c.put(req, copy));
        }
        return res;
      }))
    );
    return;
  }

  // Navigations / HTML — network-first with offline fallback to cached '/'.
  if (req.mode === 'navigate' || (req.headers.get('accept') || '').includes('text/html')) {
    event.respondWith(
      fetch(req).catch(() => caches.match('/'))
    );
  }
});
