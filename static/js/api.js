const BASE = "/api/v1";
const TOKEN_KEY = "gm.token";

export function getToken() { return localStorage.getItem(TOKEN_KEY); }
export function setToken(t) { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); }

async function request(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const token = getToken();
  if (token) headers.Authorization = "Bearer " + token;
  const res = await fetch(BASE + path, { ...options, headers });
  let body = null;
  try { body = await res.json(); } catch { /* empty body */ }
  if (!res.ok) {
    if (res.status === 401) setToken(null);
    const detail = body && body.detail ? (typeof body.detail === "string" ? body.detail : "Validation error") : `Request failed (${res.status})`;
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  return body;
}

export const api = {
  get: (path) => request(path),
  post: (path, data) => request(path, { method: "POST", body: JSON.stringify(data ?? {}) }),
  patch: (path, data) => request(path, { method: "PATCH", body: JSON.stringify(data ?? {}) }),
  del: (path) => request(path, { method: "DELETE" }),
};
