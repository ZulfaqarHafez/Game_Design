/* Service worker: makes repeat visits fast and the shell available offline.
   - Own files (HTML, JS, CSS): network first, cached copy if offline. Always fresh when online.
   - Chart library and fonts (versioned CDN URLs): cache first, they never change.
   - API: not touched, except the strategy list, which is network first with a cached fallback. */
var CACHE = "gsl-static-v1";
var CDN = /(cdn\.jsdelivr\.net|fonts\.googleapis\.com|fonts\.gstatic\.com)/;
self.addEventListener("install", function (e) { self.skipWaiting(); });
self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) { return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); })); })
    .then(function () { return self.clients.claim(); }));
});
self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET") return;
  var url = new URL(req.url);
  if (CDN.test(url.host)) {
    e.respondWith(caches.open(CACHE).then(function (c) {
      return c.match(req).then(function (hit) {
        return hit || fetch(req).then(function (res) { if (res.ok) c.put(req, res.clone()); return res; });
      });
    }));
    return;
  }
  if (url.origin !== location.origin) return;
  if (url.pathname.startsWith("/api/") && url.searchParams.get("op") !== "strategies") return;
  e.respondWith(fetch(req).then(function (res) {
    if (res.ok) caches.open(CACHE).then(function (c) { c.put(req, res.clone()); });
    return res;
  }).catch(function () { return caches.match(req).then(function (hit) { return hit || Response.error(); }); }));
});
