self.addEventListener('install', event => event.waitUntil(caches.open('pointlabs-shell-v1').then(cache => cache.addAll(['/auth/login','/static/app.css']))));
self.addEventListener('fetch', event => { if (event.request.method === 'GET' && new URL(event.request.url).origin === location.origin) event.respondWith(caches.match(event.request).then(hit => hit || fetch(event.request))); });
