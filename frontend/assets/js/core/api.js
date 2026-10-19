// Centralized HTTP client + auth state + configurable API base URL + error formatting.
const TOKEN_KEY = "awp_token";
const USER_KEY = "awp_user";
const API_BASE_KEY = "awp_api_base";

export function getApiBase() {
  if (typeof window !== "undefined") {
    if (window.AWP_CONFIG && typeof window.AWP_CONFIG.apiBaseUrl === "string") {
      return window.AWP_CONFIG.apiBaseUrl.replace(/\/+$/, "");
    }
    const meta = document.querySelector?.('meta[name="awp-api-base"]');
    if (meta && meta.content && meta.content.trim()) {
      return meta.content.trim().replace(/\/+$/, "");
    }
    const saved = localStorage.getItem(API_BASE_KEY);
    if (saved && saved.trim()) {
      return saved.trim().replace(/\/+$/, "");
    }
  }
  return "";
}

export function setApiBase(url) {
  const clean = (url || "").trim().replace(/\/+$/, "");
  if (clean) localStorage.setItem(API_BASE_KEY, clean);
  else localStorage.removeItem(API_BASE_KEY);
}

export const auth = {
  get token() { return localStorage.getItem(TOKEN_KEY) || ""; },
  set token(v) { v ? localStorage.setItem(TOKEN_KEY, v) : localStorage.removeItem(TOKEN_KEY); },
  get user() {
    try { return JSON.parse(localStorage.getItem(USER_KEY) || "null"); }
    catch { return null; }
  },
  set user(u) { u ? localStorage.setItem(USER_KEY, JSON.stringify(u)) : localStorage.removeItem(USER_KEY); },
  clear() { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY); },
  hasRole(...roles) {
    const u = this.user;
    return !!(u && roles.includes(u.role));
  },
};

function formatErrorDetail(data, status) {
  if (!data) return `Request failed with status ${status}`;
  if (typeof data.detail === "string" && data.detail.trim()) return data.detail;
  if (Array.isArray(data.detail)) {
    return data.detail
      .map(err => {
        const loc = Array.isArray(err.loc) ? err.loc.filter(p => p !== "body").join(".") : "";
        return loc ? `${loc}: ${err.msg || "Invalid value"}` : (err.msg || "Invalid value");
      })
      .join("; ");
  }
  if (data.detail && typeof data.detail === "object") {
    return data.detail.message || JSON.stringify(data.detail);
  }
  if (typeof data.message === "string" && data.message.trim()) return data.message;
  return `Request failed with status ${status}`;
}

async function request(method, path, body, opts = {}) {
  const headers = opts.headers ? { ...opts.headers } : {};
  if (auth.token) headers["Authorization"] = "Bearer " + auth.token;
  let payload = body;
  if (body && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const base = getApiBase();
  const fullUrl = path.startsWith("http://") || path.startsWith("https://")
    ? path
    : `${base}${path}`;

  let res;
  try {
    res = await fetch(fullUrl, { method, headers, body: payload });
  } catch (networkErr) {
    const err = new Error(
      navigator.onLine === false
        ? "You are currently offline. Live POS and workshop operations require an active backend connection."
        : "Unable to reach the backend server. Please verify the server is running and try again."
    );
    err.status = 0;
    err.offline = true;
    throw err;
  }

  if (res.status === 401 && !path.startsWith("/api/auth/login")) {
    auth.clear();
    window.dispatchEvent(new CustomEvent("awp:unauthorized"));
  }
  if (opts.raw) return res;
  const ct = res.headers.get("content-type") || "";
  const data = ct.includes("application/json") ? await res.json().catch(() => null) : await res.text();
  if (!res.ok) {
    const msg = formatErrorDetail(data, res.status);
    const err = new Error(msg);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

export const api = {
  get: (p, opts) => request("GET", p, undefined, opts),
  post: (p, b, opts) => request("POST", p, b, opts),
  put: (p, b, opts) => request("PUT", p, b, opts),
  del: (p, opts) => request("DELETE", p, undefined, opts),
};
