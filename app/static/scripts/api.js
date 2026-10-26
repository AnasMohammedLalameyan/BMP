/* The only place the browser talks to the server. Every call sends the session cookie and, for anything that
   changes data, the CSRF token; errors come back as ApiError with the server's message and per-field messages. */

import { state } from "./state.js";

export class ApiError extends Error {
  constructor(status, code, message, fields) {
    super(message);
    this.status = status;
    this.code = code;
    this.fields = fields || {};
  }
}

function qs(params) {
  const p = new URLSearchParams();
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") p.append(k, v);
  });
  const s = p.toString();
  return s ? "?" + s : "";
}

async function request(method, path, { params, body, form } = {}) {
  const headers = {};
  if (method !== "GET" && state.csrf) headers["X-CSRF-Token"] = state.csrf;
  let payload;
  if (form) payload = form;
  else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
  let res;
  try {
    res = await fetch("/api" + path + qs(params), { method, headers, body: payload, credentials: "same-origin" });
  } catch (e) {
    throw new ApiError(0, "network", "Could not reach the server. Check your connection and try again.");
  }
  let data = null;
  const text = await res.text();
  if (text) { try { data = JSON.parse(text); } catch (e) { data = null; } }
  if (!res.ok) {
    const err = (data && data.error) || {};
    const error = new ApiError(res.status, err.code || "error", err.message || `Request failed (${res.status})`, err.fields);
    if (res.status === 401 && path !== "/auth/login") window.dispatchEvent(new CustomEvent("bmp:unauthenticated"));
    throw error;
  }
  return data;
}

export const get = (path, params) => request("GET", path, { params });
export const post = (path, body, params) => request("POST", path, { body: body === undefined ? {} : body, params });
export const patch = (path, body) => request("PATCH", path, { body });
export const put = (path, body) => request("PUT", path, { body });
export const upload = (path, form) => request("POST", path, { form });

/** Download a file the server generates (Excel, CSV, a stored document). */
export async function download(path, params, fallbackName) {
  const res = await fetch("/api" + path + qs(params), { credentials: "same-origin" });
  if (!res.ok) {
    let msg = `Download failed (${res.status})`;
    try { msg = (await res.json()).error.message; } catch (e) { /* keep default */ }
    throw new ApiError(res.status, "download", msg);
  }
  const blob = await res.blob();
  const cd = res.headers.get("Content-Disposition") || "";
  const m = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(cd);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = m ? decodeURIComponent(m[1]) : fallbackName || "download";
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { a.remove(); URL.revokeObjectURL(url); }, 200);
}

/* ---- named calls ---- */
export const login = (email, password) => post("/auth/login", { email, password });
export const logout = () => post("/auth/logout");
export const me = () => get("/auth/me");
export const getMeta = () => get("/meta");
export const getCompanies = () => get("/companies");
export const getYears = (id) => get(`/companies/${id}/years`);
export const getOverview = (id, fy) => get(`/companies/${id}/overview`, { fy });
export const listEntity = (key, params) => get(`/entities/${key}`, params);
export const getRecord = (key, pk) => get(`/entities/${key}/${encodeURIComponent(pk)}`);
export const createRecord = (key, body) => post(`/entities/${key}`, body);
export const updateRecord = (key, pk, body) => patch(`/entities/${key}/${encodeURIComponent(pk)}`, body);
export const archiveRecord = (key, pk) => post(`/entities/${key}/${encodeURIComponent(pk)}/archive`);
export const restoreRecord = (key, pk) => post(`/entities/${key}/${encodeURIComponent(pk)}/restore`);
export const recordHistory = (key, pk) => get(`/entities/${key}/${encodeURIComponent(pk)}/history`);
export const getOptions = (entity, params) => get(`/options/${entity}`, params);
