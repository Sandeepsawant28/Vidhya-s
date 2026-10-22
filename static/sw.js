// Service worker for Vidya's Liquor Loft
// Saves only design files (CSS, JS, icons). Pages and data are NEVER saved,
// so every device always shows the live data from the server.
const CACHE_NAME = 'liquor-loft-v2';
const STATIC_ASSETS = [
  '/static/css/style.css',
  '/static/css/receipt.css',
  '/static/css/dashboard.css',
  '/static/js/main.js',
  '/static/js/pos.js',
  '/static/manifest.json'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => Promise.all(
        STATIC_ASSETS.map(url => cache.add(url).catch(() => null))
      ))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // Design files: try the network first, keep a copy, fall back to the copy.
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      fetch(req)
        .then(res => {
          if (res.status === 200) {
            const copy = res.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(req, copy));
          }
          return res;
        })
        .catch(() => caches.match(req))
    );
    return;
  }

  // Pages: always live. If the server can't be reached, say so instead of
  // showing an old page with old numbers.
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req).catch(() => new Response(
        'Cannot reach the shop server. Check the internet or Wi-Fi and try again.',
        { status: 503, headers: { 'Content-Type': 'text/plain; charset=utf-8' } }
      ))
    );
  }
});