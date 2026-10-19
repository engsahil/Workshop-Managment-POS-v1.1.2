// Application shell, hash router, theme manager, PWA installer, global search, and notification center.
import { api, auth } from "./api.js";
import { $, esc, fmtDateTime, fmtPKR, icon, openModal, toast } from "./ui.js";
import { pages } from "../pages/index.js";

const THEME_KEY = "awp_theme";

const NAV_ITEMS = [
  { section: "Operations" },
  { path: "/dashboard", label: "Dashboard", iconName: "dashboard", roles: ["admin", "manager", "cashier"] },
  { path: "/pos", label: "POS Billing", iconName: "pos", roles: ["admin", "manager", "cashier"] },
  { path: "/jobs", label: "Job Cards", iconName: "jobs", roles: ["admin", "manager", "cashier"] },
  { path: "/invoices", label: "Invoices", iconName: "invoices", roles: ["admin", "manager", "cashier"] },
  { path: "/shifts", label: "Cash Shifts", iconName: "shifts", roles: ["admin", "manager", "cashier"] },
  { section: "Workshop & Stock" },
  { path: "/customers", label: "Customers", iconName: "customers", roles: ["admin", "manager", "cashier"] },
  { path: "/vehicles", label: "Vehicles", iconName: "vehicles", roles: ["admin", "manager", "cashier"] },
  { path: "/products", label: "Parts & Inventory", iconName: "products", roles: ["admin", "manager", "cashier"] },
  { path: "/services", label: "Services & Labor", iconName: "services", roles: ["admin", "manager", "cashier"] },
  { path: "/purchases", label: "Purchases & Suppliers", iconName: "purchases", roles: ["admin", "manager"] },
  { path: "/returns", label: "Returns & Warranty", iconName: "returns", roles: ["admin", "manager", "cashier"] },
  { section: "Finance & Admin" },
  { path: "/expenses", label: "Expenses", iconName: "expenses", roles: ["admin", "manager"] },
  { path: "/staff", label: "Mechanics & Staff", iconName: "staff", roles: ["admin", "manager"] },
  { path: "/reports", label: "Reports & Analytics", iconName: "reports", roles: ["admin", "manager"] },
  { path: "/users", label: "Users & Roles", iconName: "users", roles: ["admin"] },
  { path: "/settings", label: "Settings", iconName: "settings", roles: ["admin"] },
  { path: "/backups", label: "Backup & Restore", iconName: "backups", roles: ["admin"] },
  { path: "/audit", label: "Audit Log", iconName: "audit", roles: ["admin", "manager"] },
  { path: "/legal", label: "Privacy & Terms", iconName: "legal", roles: ["admin", "manager", "cashier"] },
  { path: "/help", label: "Help & Guide", iconName: "help", roles: ["admin", "manager", "cashier"] },
];

export const appState = {
  business: { business_name: "Auto Workshop", currency: "PKR" },
  currentShift: null,
};

/* ---------------- Theme Manager (Light default: White + Off-White + Beach) ---------------- */
function initTheme() {
  const saved = localStorage.getItem(THEME_KEY) || "light";
  applyTheme(saved);
  const btn = $("#btn-theme");
  if (btn) {
    btn.onclick = () => {
      const cur = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
      const next = cur === "dark" ? "light" : "dark";
      localStorage.setItem(THEME_KEY, next);
      applyTheme(next);
    };
  }
}

function applyTheme(theme) {
  const clean = theme === "dark" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", clean);
  const metaTheme = $("#meta-theme-color");
  if (metaTheme) {
    metaTheme.setAttribute("content", clean === "dark" ? "#161513" : "#FAF9F6");
  }
  const btn = $("#btn-theme");
  if (btn) {
    btn.innerHTML = clean === "dark" ? icon("sun", 16) : icon("moon", 16);
    btn.title = clean === "dark" ? "Switch to Light Mode (White + Beach)" : "Switch to Dark Mode";
  }
}

/* ---------------- PWA Service Worker & Install Manager ---------------- */
let deferredInstallPrompt = null;

function isStandaloneMode() {
  return (
    window.matchMedia?.("(display-mode: standalone)").matches ||
    window.navigator.standalone === true
  );
}

function initPWA() {
  const installBtn = $("#btn-install-app");
  const offlineBanner = $("#offline-banner");

  const syncOnlineState = () => {
    if (offlineBanner) {
      offlineBanner.hidden = navigator.onLine !== false;
    }
  };
  window.addEventListener("online", syncOnlineState);
  window.addEventListener("offline", syncOnlineState);
  syncOnlineState();

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {
        // Non-HTTPS non-localhost environments may decline SW registration; ignore silently.
      });
    });
  }

  if (installBtn) {
    if (isStandaloneMode()) {
      installBtn.hidden = true;
    }

    window.addEventListener("beforeinstallprompt", (e) => {
      e.preventDefault();
      deferredInstallPrompt = e;
      if (!isStandaloneMode()) {
        installBtn.hidden = false;
      }
    });

    window.addEventListener("appinstalled", () => {
      deferredInstallPrompt = null;
      installBtn.hidden = true;
      toast("Auto Workshop POS installed as an app", "ok");
    });

    installBtn.onclick = async () => {
      if (deferredInstallPrompt) {
        try {
          deferredInstallPrompt.prompt();
          const choice = await deferredInstallPrompt.userChoice;
          if (choice && choice.outcome === "accepted") {
            deferredInstallPrompt = null;
            installBtn.hidden = true;
          }
        } catch {
          showInstallGuidanceModal();
        }
      } else {
        showInstallGuidanceModal();
      }
    };
  }
}

function showInstallGuidanceModal() {
  const standalone = isStandaloneMode();
  openModal({
    title: "Install Auto Workshop Management POS",
    body: standalone
      ? `<p>Auto Workshop Management POS is already running in installed standalone mode.</p>
         <div class="modal-foot"><button class="btn btn-primary" data-close>Close</button></div>`
      : `<div style="line-height:1.65;font-size:13.5px">
           <p style="margin-top:0">Install <b>Auto Workshop Management POS</b> for quick launch from your desktop, taskbar, or mobile home screen:</p>
           <div class="card" style="background:var(--bg-subtle);padding:12px;margin-bottom:10px">
             <b>Google Chrome / Microsoft Edge (Windows, macOS, Linux, Android)</b>
             <div class="muted" style="margin-top:4px">
               Click the <b>Install App</b> icon in the browser address bar (right side) or open the browser menu (<b>⋮</b> / <b>⋯</b>) &rarr; <b>Apps / Cast, save, and share</b> &rarr; <b>Install Auto Workshop Management POS</b>.
             </div>
           </div>
           <div class="card" style="background:var(--bg-subtle);padding:12px;margin-bottom:10px">
             <b>Apple Safari (iPhone / iPad / macOS)</b>
             <div class="muted" style="margin-top:4px">
               Tap the <b>Share</b> button in Safari and choose <b>Add to Home Screen</b> (or <b>Add to Dock</b> on macOS Sonoma+).
             </div>
           </div>
           <div class="muted" style="font-size:12px">
             Note: Browser installation requires accessing the app over <code>http://localhost</code>, <code>http://127.0.0.1</code>, or <code>https://</code>.
           </div>
         </div>
         <div class="modal-foot">
           <button type="button" class="btn btn-primary" data-close>Got it</button>
         </div>`,
  });
}

function renderNav() {
  const nav = $("#sidebar-nav");
  const u = auth.user;
  if (!u || !nav) return;
  const html = [];
  for (const item of NAV_ITEMS) {
    if (item.section) {
      html.push(`<div class="nav-section">${esc(item.section)}</div>`);
      continue;
    }
    if (!item.roles.includes(u.role)) continue;
    html.push(`
      <a class="nav-item" data-route="${item.path}" href="#${item.path}">
        <span class="nav-ic">${icon(item.iconName, 16)}</span>
        <span>${esc(item.label)}</span>
      </a>
    `);
  }
  nav.innerHTML = html.join("");
}

function renderUserChip() {
  const u = auth.user;
  if (!u) return;
  $("#user-chip").innerHTML = `
    <span class="u-name">${esc(u.full_name)}</span>
    <span class="u-role">${esc(u.role)}</span>
  `;
}

export async function refreshBusinessHeader() {
  try {
    const b = await api.get("/api/settings/business");
    appState.business = b;
    $("#sidebar-biz-name").textContent = b.business_name || "Auto Workshop";
    const logoBox = $("#sidebar-logo");
    if (b.logo_path) {
      logoBox.innerHTML = `<img src="${esc(b.logo_path)}" alt="logo" style="width:100%;height:100%;object-fit:cover;border-radius:6px"/>`;
    } else {
      logoBox.textContent = (b.business_name || "AW").slice(0, 2).toUpperCase();
    }
  } catch { /* ignore */ }
  try {
    const sh = await api.get("/api/shifts/current");
    appState.currentShift = sh;
    const pill = $("#sidebar-shift-pill");
    if (sh) {
      pill.textContent = `Shift #${sh.shift_number} open`;
      pill.style.color = "var(--success)";
    } else {
      pill.textContent = "Shift closed";
      pill.style.color = "";
    }
  } catch { /* ignore */ }
}

export const refreshHeaderContext = refreshBusinessHeader;

export async function refreshNotifications() {
  try {
    const data = await api.get("/api/notifications?limit=25");
    const badgeEl = $("#notif-badge");
    if (data.unread > 0) {
      badgeEl.hidden = false;
      badgeEl.textContent = data.unread > 99 ? "99+" : String(data.unread);
    } else {
      badgeEl.hidden = true;
    }
    return data;
  } catch { return { items: [], unread: 0 }; }
}

export async function showDailyClosingSummaryModal(forDate = "") {
  try {
    const q = forDate ? `?for_date=${encodeURIComponent(forDate)}` : "";
    const s = await api.get(`/api/notifications/daily-summary${q}`);
    const m = openModal({
      title: `Daily Closing Summary — ${s.date}`,
      size: "lg",
      body: `
        <div class="toolbar" style="margin-bottom:14px">
          <label style="margin:0;display:flex;align-items:center;gap:8px">
            <span>Business Date</span>
            <input type="date" id="dcs-date" value="${esc(s.date)}" style="width:auto" />
          </label>
          <button class="btn btn-ghost btn-sm" id="dcs-load">Load Date</button>
          <div class="spacer"></div>
          <button class="btn btn-primary btn-sm" id="dcs-post">Record Closing Notification</button>
        </div>
        <div class="kpi-grid">
          <div class="kpi">
            <div class="k-label">Invoices Count</div>
            <div class="k-value">${s.invoices_count}</div>
            <div class="k-sub">${s.credit_sales_count} credit sale(s)</div>
          </div>
          <div class="kpi success">
            <div class="k-label">Gross Sales</div>
            <div class="k-value">${fmtPKR(s.sales_total_paisa)}</div>
            <div class="k-sub">Credit issued: ${fmtPKR(s.credit_sales_paisa)}</div>
          </div>
          <div class="kpi info">
            <div class="k-label">Payments Collected</div>
            <div class="k-value">${fmtPKR(s.collected_paisa)}</div>
            <div class="k-sub">Across all payment methods</div>
          </div>
          <div class="kpi warn">
            <div class="k-label">Expenses (${s.expenses_count})</div>
            <div class="k-value">${fmtPKR(s.expenses_total_paisa)}</div>
            <div class="k-sub">Recorded for ${esc(s.date)}</div>
          </div>
          <div class="kpi ${s.net_cash_flow_paisa >= 0 ? "success" : "danger"}">
            <div class="k-label">Net Cash Flow</div>
            <div class="k-value">${fmtPKR(s.net_cash_flow_paisa)}</div>
            <div class="k-sub">Collected minus expenses</div>
          </div>
          <div class="kpi">
            <div class="k-label">Jobs Completed</div>
            <div class="k-value">${s.jobs_completed_count}</div>
            <div class="k-sub">${s.low_stock_count} low-stock · ${s.out_of_stock_count} out-of-stock</div>
          </div>
        </div>
        <div class="modal-foot">
          <button class="btn btn-ghost" data-close>Close</button>
        </div>
      `,
    });
    m.root.querySelector("#dcs-load").onclick = () => {
      const dt = m.root.querySelector("#dcs-date").value;
      m.close();
      showDailyClosingSummaryModal(dt);
    };
    m.root.querySelector("#dcs-post").onclick = async () => {
      const dt = m.root.querySelector("#dcs-date").value;
      await api.post(`/api/notifications/daily-summary?for_date=${encodeURIComponent(dt)}`);
      toast("Daily closing summary recorded to notifications");
      await refreshNotifications();
    };
  } catch (err) {
    toast(err.message, "err");
  }
}

export const openDailySummaryModal = showDailyClosingSummaryModal;

function getNotificationRoute(item) {
  const rt = (item.related_type || "").toLowerCase();
  const rid = item.related_id;
  if (rt === "product") return "#/products?low=1";
  if (rt === "job" || rt === "job_card") return rid ? `#/jobs?id=${rid}` : "#/jobs";
  if (rt === "invoice" || rt === "payment" || rt === "sale_return") return rid ? `#/invoices?id=${rid}` : "#/invoices";
  if (rt === "purchase" || rt === "purchase_order") return "#/purchases";
  if (rt === "warranty_claim" || rt === "claim") return "#/returns?tab=claims";
  if (rt === "shift") return "#/shifts";
  if (rt === "daily_summary") return "__daily_summary__";
  if (item.type === "low_stock") return "#/products?low=1";
  if (item.type === "job") return "#/jobs";
  if (item.type === "payment" || item.type === "credit_due") return "#/invoices";
  if (item.type === "warranty") return "#/returns?tab=claims";
  return "";
}

async function toggleNotificationsDrawer() {
  const dr = $("#notif-drawer");
  if (!dr.hidden) { dr.hidden = true; return; }
  const data = await api.get("/api/notifications?limit=40");
  dr.innerHTML = `
    <div class="flex-between" style="margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid var(--border)">
      <strong>Notifications (${data.unread} unread)</strong>
      <div class="flex">
        <button class="btn btn-ghost btn-sm" id="btn-daily-summary" title="View Daily Closing Summary">Daily Summary</button>
        <button class="btn btn-ghost btn-sm" id="btn-mark-all-read">Mark all read</button>
      </div>
    </div>
    <div id="notif-list">
      ${data.items.length === 0 ? `<div class="empty">No notifications yet.</div>` :
        data.items.map(n => `
          <div class="notif-item ${n.is_read ? "" : "unread"}" data-nid="${n.id}" data-route="${esc(getNotificationRoute(n))}">
            <div class="n-head">
              <div class="n-title">${esc(n.title)}</div>
              ${!n.is_read ? `<button class="btn btn-ghost btn-sm" data-mark-one="${n.id}" style="padding:1px 6px;font-size:10.5px">Mark read</button>` : ""}
            </div>
            ${n.message ? `<div class="n-msg">${esc(n.message)}</div>` : ""}
            <div class="n-time">${fmtDateTime(n.created_at)}</div>
          </div>
        `).join("")}
    </div>
  `;
  dr.hidden = false;

  $("#btn-daily-summary").onclick = (e) => {
    e.stopPropagation();
    dr.hidden = true;
    showDailyClosingSummaryModal();
  };

  $("#btn-mark-all-read").onclick = async (e) => {
    e.stopPropagation();
    await api.post("/api/notifications/read-all");
    await refreshNotifications();
    dr.hidden = true;
  };

  dr.querySelectorAll("[data-mark-one]").forEach(btn => {
    btn.onclick = async (e) => {
      e.stopPropagation();
      const nid = Number(btn.dataset.markOne);
      await api.post("/api/notifications/read", { ids: [nid] });
      await refreshNotifications();
      toggleNotificationsDrawer();
      toggleNotificationsDrawer();
    };
  });

  dr.querySelectorAll(".notif-item").forEach(row => {
    row.onclick = async () => {
      const nid = Number(row.dataset.nid);
      if (row.classList.contains("unread")) {
        await api.post("/api/notifications/read", { ids: [nid] });
        await refreshNotifications();
      }
      const targetRoute = row.dataset.route;
      dr.hidden = true;
      if (targetRoute === "__daily_summary__") {
        showDailyClosingSummaryModal();
      } else if (targetRoute) {
        location.hash = targetRoute;
      }
    };
  });
}

function setupGlobalSearch() {
  const input = $("#global-search");
  const box = $("#global-search-results");
  let timer = null;

  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      input.focus();
      input.select();
    } else if (e.key === "F2") {
      e.preventDefault();
      location.hash = "#/pos";
    }
  });

  input.addEventListener("input", () => {
    clearTimeout(timer);
    const q = input.value.trim();
    if (q.length < 2) { box.hidden = true; return; }
    timer = setTimeout(async () => {
      try {
        const [custs, vehs, invs, jobs] = await Promise.all([
          api.get(`/api/customers?q=${encodeURIComponent(q)}&page_size=5`),
          api.get(`/api/vehicles?q=${encodeURIComponent(q)}&page_size=5`),
          api.get(`/api/invoices?q=${encodeURIComponent(q)}&page_size=5`),
          api.get(`/api/jobs?q=${encodeURIComponent(q)}&page_size=5`),
        ]);
        const rows = [];
        for (const c of custs.items || []) rows.push({ label: `Customer · ${c.name}`, sub: c.phone || c.code, href: `#/customers?id=${c.id}` });
        for (const v of vehs.items || []) rows.push({ label: `Vehicle · ${v.registration_no}`, sub: `${v.make} ${v.model} (${v.customer_name || ""})`, href: `#/vehicles?id=${v.id}` });
        for (const j of jobs.items || []) rows.push({ label: `Job · ${j.job_number}`, sub: `${j.customer_name || ""} · ${j.status}`, href: `#/jobs?id=${j.id}` });
        for (const i of invs.items || []) rows.push({ label: `Invoice · ${i.invoice_number}`, sub: fmtPKR(i.total_paisa), href: `#/invoices?id=${i.id}` });
        if (rows.length === 0) {
          box.innerHTML = `<div class="sd-row muted">No matches for "${esc(q)}"</div>`;
        } else {
          box.innerHTML = rows.map(r => `
            <div class="sd-row" data-href="${esc(r.href)}">
              <span>${esc(r.label)}</span>
              <span class="muted">${esc(r.sub || "")}</span>
            </div>`).join("");
          box.querySelectorAll(".sd-row[data-href]").forEach(el => {
            el.onclick = () => { box.hidden = true; input.value = ""; location.hash = el.dataset.href; };
          });
        }
        box.hidden = false;
      } catch { box.hidden = true; }
    }, 180);
  });

  document.addEventListener("click", (e) => {
    if (!e.target.closest(".topbar-search")) box.hidden = true;
    if (!e.target.closest("#notif-drawer") && !e.target.closest("#btn-notif")) {
      $("#notif-drawer").hidden = true;
    }
  });
}

async function route() {
  const raw = location.hash.replace(/^#/, "") || "/dashboard";
  const [path, qs] = raw.split("?");
  const params = new URLSearchParams(qs || "");

  // Public legal viewer works even before login
  if (!auth.token) {
    if (path.startsWith("/legal/")) {
      const key = path.split("/")[2];
      await pages.legalPublic(key);
    }
    return;
  }

  const root = $("#page-root");
  if (path.startsWith("/legal/")) {
    const key = path.split("/")[2];
    $("#page-title").textContent = key === "terms_conditions" ? "Terms & Conditions" : "Privacy Policy";
    await pages.legal(root, key);
    return;
  }

  const routeKey = path.replace(/^\/+/, "") || "dashboard";
  const pageEntry = Array.isArray(pages)
    ? (pages.find(p => p.route === routeKey) || pages.find(p => p.route === "dashboard"))
    : null;

  const navItem = NAV_ITEMS.find(n => n.path === path);
  $("#page-title").textContent = navItem ? navItem.label : (pageEntry?.title || "Dashboard");
  document.querySelectorAll(".nav-item").forEach(a => {
    a.classList.toggle("active", a.dataset.route === path);
  });
  $("#sidebar").classList.remove("open");

  try {
    if (pageEntry && typeof pageEntry.load === "function") {
      const renderFn = await pageEntry.load();
      await renderFn(root, params);
    } else if (typeof pages[routeKey] === "function") {
      await pages[routeKey](root, params);
    } else {
      const fallback = await pages[0].load();
      await fallback(root, params);
    }
  } catch (err) {
    root.innerHTML = `
      <div class="card">
        <div class="form-error" style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:0">
          <span>${esc(err.message || "Failed to load page")}</span>
          <button class="btn btn-ghost btn-sm" id="page-retry-btn">Retry</button>
        </div>
      </div>`;
    const retryBtn = root.querySelector("#page-retry-btn");
    if (retryBtn) retryBtn.onclick = () => route();
  }
}

async function boot() {
  initTheme();
  initPWA();
  const status = await api.get("/api/auth/setup-status").catch(() => ({ needs_setup: false }));
  if (status.needs_setup) {
    auth.clear();
    showAuthView(true);
    return;
  }
  if (!auth.token) {
    showAuthView(false);
    return;
  }
  try {
    const me = await api.get("/api/auth/me");
    auth.user = me;
    showAppShell();
  } catch {
    auth.clear();
    showAuthView(false);
  }
}

function showAuthView(isSetup) {
  $("#app-shell").hidden = true;
  $("#auth-view").hidden = false;
  $("#login-form").hidden = isSetup;
  $("#setup-form").hidden = !isSetup;
  $("#auth-subtitle").textContent = isSetup
    ? "First-time setup — create administrator account"
    : "Sign in to continue";
}

function showAppShell() {
  $("#auth-view").hidden = true;
  $("#app-shell").hidden = false;
  renderNav();
  renderUserChip();
  refreshBusinessHeader();
  refreshNotifications();
  if (!location.hash || location.hash === "#/" || location.hash.startsWith("#/legal/")) {
    location.hash = "#/dashboard";
  }
  route();
}

if (typeof document !== "undefined") {
  $("#login-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const errBox = $("#login-error");
    errBox.hidden = true;
    const fd = new FormData(e.target);
    try {
      const res = await api.post("/api/auth/login", {
        username: fd.get("username"),
        password: fd.get("password"),
      });
      auth.token = res.access_token;
      auth.user = res.user;
      e.target.reset();
      showAppShell();
    } catch (err) {
      errBox.textContent = err.message;
      errBox.hidden = false;
    }
  });

  $("#setup-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const errBox = $("#setup-error");
    errBox.hidden = true;
    const fd = new FormData(e.target);
    if (fd.get("password") !== fd.get("password_confirm")) {
      errBox.textContent = "Passwords do not match";
      errBox.hidden = false;
      return;
    }
    try {
    const res = await api.post("/api/auth/setup", {
      username: fd.get("username"),
      full_name: fd.get("full_name"),
      password: fd.get("password"),
      password_confirm: fd.get("password_confirm"),
    });
      auth.token = res.access_token;
      auth.user = res.user;
      toast("Administrator account created");
      showAppShell();
    } catch (err) {
      errBox.textContent = err.message;
      errBox.hidden = false;
    }
  });

  $("#btn-logout")?.addEventListener("click", async () => {
    try { await api.post("/api/auth/logout"); } catch { /* ignore */ }
    auth.clear();
    showAuthView(false);
  });

  $("#btn-notif")?.addEventListener("click", toggleNotificationsDrawer);
  $("#btn-toggle-sidebar")?.addEventListener("click", () => {
    $("#sidebar").classList.toggle("open");
  });

  window.addEventListener("hashchange", route);
  window.addEventListener("awp:unauthorized", () => showAuthView(false));

  setupGlobalSearch();
  boot();
}
