const CACHE_VERSION = "shtjk-currency-v3";

const STATIC_CACHE = `${CACHE_VERSION}-static`;
const DATA_CACHE = `${CACHE_VERSION}-data`;

const STATIC_FILES = [
  "./",
  "./index.html",
  "./manifest.json",
  "./icons/icon-192.png",
  "./icons/icon-512.png"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(cache => cache.addAll(STATIC_FILES))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(keys =>
        Promise.all(
          keys
            .filter(key =>
              key !== STATIC_CACHE &&
              key !== DATA_CACHE
            )
            .map(key => caches.delete(key))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  const request = event.request;

  if (request.method !== "GET") return;

  const url = new URL(request.url);

  /*
   * Курсы валют:
   * всегда сначала пытаемся получить
   * свежий rates.json.
   *
   * Если интернета нет —
   * используем последний сохранённый.
   */
  if (url.pathname.endsWith("/api/rates.json")) {

    event.respondWith(
      fetch(request, {
        cache: "no-store"
      })
      .then(response => {

        if (!response.ok) {
          throw new Error("Rates request failed");
        }

        const copy = response.clone();

        caches.open(DATA_CACHE)
          .then(cache => {
            cache.put(request, copy);
          });

        return response;
      })
      .catch(() =>
        caches.match(request)
      )
    );

    return;
  }

  /*
   * Файлы приложения:
   * сначала кэш,
   * затем сеть.
   */
  event.respondWith(
    caches.match(request)
      .then(cached => {

        if (cached) {
          return cached;
        }

        return fetch(request)
          .then(response => {

            if (
              response.ok &&
              response.type === "basic"
            ) {

              const copy = response.clone();

              caches.open(STATIC_CACHE)
                .then(cache => {
                  cache.put(request, copy);
                });
            }

            return response;
          });

      })
  );
});