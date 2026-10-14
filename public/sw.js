// Data is network-first. Offline copies retain their original verification time.
const CACHE = "russia-auto-v1-__BUILD_ID__";
const SHELL = [
  "./",
  "./index.html",
  "./styles.css",
  "./app.js",
  "./lib.js",
  "./manifest.webmanifest",
  "./icon.svg",
  "./icon-192.png",
  "./icon-512.png",
  "./apple-touch-icon.png",
  "./data/current.json",
  "./data/history.json",
];
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(SHELL))
      .then(() => self.skipWaiting()),
  );
});
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => k.startsWith("russia-auto-v1-") && k !== CACHE)
            .map((k) => caches.delete(k)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});
self.addEventListener("fetch", (event) => {
  if (
    event.request.method !== "GET" ||
    new URL(event.request.url).origin !== location.origin
  )
    return;
  event.respondWith(
    (async () => {
      try {
        const response = await fetch(event.request);
        if (response.ok) {
          const copy = response.clone();
          const cache = await caches.open(CACHE);
          await cache.put(event.request, copy);
        }
        return response;
      } catch {
        const cached = await caches.match(event.request);
        if (cached) return cached;
        return new Response("Offline; this resource has not been cached", {
          status: 503,
        });
      }
    })(),
  );
});
