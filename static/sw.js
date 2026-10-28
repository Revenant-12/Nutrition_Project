const CACHE_NAME = 'aurafit-v1';
const ASSETS_TO_CACHE = [
  '/',
  '/static/index.html',
  '/static/manifest.json'
];

self.addEventListener('install', (evt) => {
  evt.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE);
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (evt) => {
  evt.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((k) => {
          if (k !== CACHE_NAME) {
            return caches.delete(k);
          }
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (evt) => {
  if (evt.request.method === 'GET' && evt.request.url.startsWith(self.location.origin)) {
    evt.respondWith(
      fetch(evt.request).catch(() => caches.match(evt.request))
    );
  }
});

