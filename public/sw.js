const CACHE_NAME = 'fli-tracker-assets-v2';
const urlsToCache = [
  '/manifest.json',
  '/apple-touch-icon.png'
];

self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames =>
      Promise.all(
        cacheNames
          .filter(name => name !== CACHE_NAME)
          .map(name => caches.delete(name))
      )
    ).then(() => clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const requestUrl = new URL(event.request.url);
  const isNavigate = event.request.mode === 'navigate';
  const isHtml = requestUrl.pathname === '/' || requestUrl.pathname.endsWith('.html');
  const isData = requestUrl.pathname.startsWith('/data/');
  const isServiceWorker = requestUrl.pathname === '/sw.js';
  // Never cache HTML, fare JSON, or the worker itself — stale Book links
  // and missed dashboard deploys are worse than a cold fetch.
  if (isNavigate || isHtml || isData || isServiceWorker) {
    event.respondWith(fetch(event.request));
    return;
  }
  event.respondWith(
    fetch(event.request)
      .then(response => {
        if (!response || response.status !== 200 || response.type !== 'basic') {
          return response;
        }
        const responseToCache = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(event.request, responseToCache));
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
