const CACHE_NAME = 'rnai-pwa-v1';
self.addEventListener('install', (evt) => {
  self.skipWaiting();
});
self.addEventListener('activate', (evt) => {
  evt.waitUntil(clients.claim());
});
self.addEventListener('fetch', (evt) => {
  if (evt.request.method === 'GET' && evt.request.url.includes('/api/')) {
    return;
  }
});
