const CACHE_NAME = "shtjk-currency-v1";

const APP_FILES = [
  "./",
  "./index.html",
  "./manifest.json",
  "./icons/icon-192.png",
  "./icons/icon-512.png"
];


self.addEventListener(
  "install",
  (event) => {

    event.waitUntil(

      caches
        .open(CACHE_NAME)
        .then((cache) => {

          return cache.addAll(
            APP_FILES
          );

        })

    );

    self.skipWaiting();

  }
);


self.addEventListener(
  "activate",
  (event) => {

    event.waitUntil(

      caches
        .keys()
        .then((keys) => {

          return Promise.all(

            keys
              .filter(
                (key) =>
                  key !== CACHE_NAME
              )
              .map(
                (key) =>
                  caches.delete(key)
              )

          );

        })

    );

    self.clients.claim();

  }
);


self.addEventListener(
  "fetch",
  (event) => {

    const request =
      event.request;


    if (
      request.method !== "GET"
    ) {
      return;
    }


    const url =
      new URL(
        request.url
      );


    /*
     * rates.json всегда
     * пытаемся получить свежий.
     */

    if (
      url.pathname.endsWith(
        "/api/rates.json"
      )
    ) {

      event.respondWith(

        fetch(
          request,
          {
            cache: "no-store"
          }
        )

          .then(
            (response) => {

              if (
                response.ok
              ) {

                const copy =
                  response.clone();


                caches
                  .open(
                    CACHE_NAME
                  )
                  .then(
                    (cache) => {

                      cache.put(
                        request,
                        copy
                      );

                    }
                  );

              }


              return response;

            }
          )

          .catch(
            () => {

              return caches.match(
                request
              );

            }
          )

      );

      return;

    }


    /*
     * Остальные файлы:
     * сначала Cache,
     * затем сеть.
     */

    event.respondWith(

      caches
        .match(request)

        .then(
          (cached) => {

            if (cached) {
              return cached;
            }


            return fetch(
              request
            )

              .then(
                (response) => {

                  if (
                    response &&
                    response.status === 200 &&
                    response.type === "basic"
                  ) {

                    const copy =
                      response.clone();


                    caches
                      .open(
                        CACHE_NAME
                      )
                      .then(
                        (cache) => {

                          cache.put(
                            request,
                            copy
                          );

                        }
                      );

                  }


                  return response;

                }
              );

          }
        )

    );

  }
);