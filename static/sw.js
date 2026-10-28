const CACHE_NAME = 'aurafit-v2';
const ASSETS_TO_CACHE = [
  '/',
  '/static/index.html',
  '/static/manifest.json'
];

self.addEventListener('install', (evt) => {
  self.skipWaiting();
});

self.addEventListener('activate', (evt) => {
  evt.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((k) => caches.delete(k))
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (evt) => {
  // Always fetch fresh network content first, fallback to cache if offline
  if (evt.request.method === 'GET' && evt.request.url.startsWith(self.location.origin)) {
    evt.respondWith(
      fetch(evt.request).catch(() => caches.match(evt.request))
    );
  }
});

