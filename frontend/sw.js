// ============================================================================
// Auto Workshop Management POS — Version 1.2.2
// Production-Safe Service Worker (Static App Shell Only)
//
// SAFETY RULES:
// 1. NEVER cache /api/* requests, authenticated responses, or private POS data.
// 2. NEVER turn failed /api/* requests into HTML navigation fallbacks.
// 3. NEVER cache non-GET requests or error responses (status !== 200).
// 4. Clean up all older cache versions automatically upon activation.
// ============================================================================

const APP_VERSION = "1.2.2";
const CACHE_NAME = `awp-shell-v${APP_VERSION}`;

const APP_SHELL_ASSETS = [
  "/",
  "/index.html",
  "/manifest.webmanifest",
  "/assets/css/app.css",
  "/assets/icons/icon-192.png",
  "/assets/icons/icon-512.png",
  "/assets/icons/icon-maskable-512.png",
  "/assets/icons/apple-touch-icon.png",
  "/assets/icons/favicon-32.png",
  "/assets/js/core/api.js",
  "/assets/js/core/app.js",
  "/assets/js/core/ui.js",
  "/assets/js/pages/index.js",
  "/assets/js/pages/dashboard.js",
  "/assets/js/pages/pos.js",
  "/assets/js/pages/invoices.js",
  "/assets/js/pages/customers.js",
  "/assets/js/pages/vehicles.js",
  "/assets/js/pages/products.js",
  "/assets/js/pages/jobs.js",
  "/assets/js/pages/services.js",
  "/assets/js/pages/staff.js",
  "/assets/js/pages/purchases.js",
  "/assets/js/pages/expenses.js",
  "/assets/js/pages/shifts.js",
  "/assets/js/pages/returns.js",
  "/assets/js/pages/reports.js",
  "/assets/js/pages/users.js",
  "/assets/js/pages/settings.js",
  "/assets/js/pages/backups.js",
  "/assets/js/pages/audit.js",
  "/assets/js/pages/legal.js",
  "/assets/js/pages/help.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_SHELL_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => k !== CACHE_NAME)
            .map((k) => caches.delete(k))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Rule 1: NEVER cache or HTML-fallback any /api/ request or cross-origin API call
  if (
    url.pathname === "/api" ||
    url.pathname.startsWith("/api/") ||
    url.origin !== self.location.origin
  ) {
    event.respondWith(
      fetch(request).catch(() =>
        new Response(
          JSON.stringify({
            detail:
              "Offline or backend server unreachable. Live POS transactions, returns, and workshop records require an active backend connection.",
            offline: true,
          }),
          {
            status: 503,
            statusText: "Service Unavailable",
            headers: { "Content-Type": "application/json" },
          }
        )
      )
    );
    return;
  }

  // Rule 2: Only handle GET requests for static app shell assets
  if (request.method !== "GET") {
    return;
  }

  // Rule 3: Never cache requests carrying an Authorization header
  if (request.headers.get("Authorization")) {
    return;
  }

  // Navigation requests: network-first, fallback to cached /index.html when offline
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((res) => {
          if (res && res.ok && res.status === 200) {
            const copy = res.clone();
            caches.open(CACHE_NAME).then((c) => c.put("/index.html", copy));
          }
          return res;
        })
        .catch(() =>
          caches.match("/index.html").then(
            (cached) =>
              cached ||
              new Response(
                "<!doctype html><html><head><meta charset='utf-8'><title>Offline — Auto Workshop POS</title></head><body style='font-family:sans-serif;padding:32px;background:#FAF9F6;color:#292824'><h2>Auto Workshop Management POS — Offline</h2><p>The backend server is currently unreachable. Start the local server or reconnect to continue POS operations.</p></body></html>",
                {
                  status: 503,
                  headers: { "Content-Type": "text/html; charset=utf-8" },
                }
              )
          )
        )
    );
    return;
  }

  // Static assets (/assets/*, /manifest.webmanifest, etc.): network-first with cache fallback
  event.respondWith(
    fetch(request)
      .then((res) => {
        if (res && res.ok && res.status === 200 && res.type === "basic") {
          const copy = res.clone();
          caches.open(CACHE_NAME).then((c) => c.put(request, copy));
        }
        return res;
      })
      .catch(() => caches.match(request))
  );
});
