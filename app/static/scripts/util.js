/* Small shared helpers, carried over from the approved dashboard (selectors, escaping, toast, CSV) and
   extended with the formatting the database's types need (dates, money, yes/no). */

export const $ = (sel, root) => (root || document).querySelector(sel);
export const $$ = (sel, root) =>
  Array.prototype.slice.call((root || document).querySelectorAll(sel));

/* Everything that came from the database or a user goes through this before it reaches innerHTML. */
export function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

export function toast(msg) {
  const el = $("#toast");
  $("#toastMsg").textContent = msg;
  if (window.bootstrap) {
    window.bootstrap.Toast.getOrCreateInstance(el, { delay: 3200 }).show();
  }
}

/* ---- financial years (April to March, written 2024-25) and the "show historical directors" switch ---- */

/** The window of a financial year as ISO dates, or null for "all years" / an unreadable value (same convention as the server). */
export function fyWindow(fy) {
  const m = /^(\d{4})-(\d{2})$/.exec(fy || "");
  if (!m || Number(m[2]) !== (Number(m[1]) + 1) % 100) return null;
  const y = Number(m[1]);
  return { start: `${y}-04-01`, end: `${y + 1}-03-31` };
}

/** Was a board stint active in the year? It began on or before the year's last day and had not ended before its first day.
    Mirrors active_in_window() in routers/people.py. ISO dates compare correctly as text. */
export function activeInFy(start, end, fy) {
  const w = fyWindow(fy);
  return !!w && start <= w.end && (!end || end >= w.start);
}

/** Did the stint end during the year? */
export function ceasedInFy(end, fy) {
  const w = fyWindow(fy);
  return !!w && !!end && end >= w.start && end <= w.end;
}

/** A register row (from /directors-register) shown by default: active in the chosen year, or - with "all years" - serving today. */
export function directorShown(row, fy) {
  return fyWindow(fy) ? activeInFy(row.start_date, row.end_date, fy) : !!row.is_current;
}

/** The "Show Historical/Ceased Directors" switch: off by default, remembered for the browser session. */
export function showHistorical(value) {
  try {
    if (value === undefined) return sessionStorage.getItem("bmp_show_historical") === "1";
    sessionStorage.setItem("bmp_show_historical", value ? "1" : "0");
  } catch (e) { /* storage blocked: the switch just resets when the page is reloaded */ }
  return !!value;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2025-04-15" -> "15 Apr 2025" (no timezone shifting: it is a calendar date, not an instant). */
export function fmtDate(s) {
  if (!s) return "";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(s));
  return m ? `${m[3]} ${MONTHS[Number(m[2]) - 1]} ${m[1]}` : String(s);
}

/** "2021-05-31" -> "31-05-2021" (the form the "Ceased on" badge uses). */
export function fmtDateDMY(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(s || ""));
  return m ? `${m[3]}-${m[2]}-${m[1]}` : String(s || "");
}

const IST = "Asia/Kolkata";

export function fmtDateTime(s) {
  if (!s) return "";
  try {
    const d = new Date(s);
    return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: IST })
      + " " + d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: IST });
  } catch (e) { return String(s); }
}

export function fmtTime(s) {
  return s ? String(s).slice(0, 5) : "";
}

/** Indian digit grouping (12,34,567.50) for money and counts. */
export function fmtNumber(v, scale) {
  if (v == null || v === "") return "";
  const n = Number(v);
  if (!Number.isFinite(n)) return String(v);
  return n.toLocaleString("en-IN", {
    minimumFractionDigits: scale != null ? Math.min(scale, 2) : 0,
    maximumFractionDigits: scale != null ? Math.min(scale, 4) : 4,
  });
}

/** datetime-local input value from an ISO instant, in India time. */
export function toLocalInput(s) {
  if (!s) return "";
  const d = new Date(s);
  const p = new Intl.DateTimeFormat("en-CA", {
    year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
    hour12: false, timeZone: IST,
  }).formatToParts(d).reduce((a, x) => { a[x.type] = x.value; return a; }, {});
  return `${p.year}-${p.month}-${p.day}T${p.hour === "24" ? "00" : p.hour}:${p.minute}`;
}

export function debounce(fn, ms) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

/* ---- file helpers (pure client side, as in the approved dashboard) ---- */

function csvEscape(v) {
  v = v == null ? "" : String(v);
  return /[",\n\r]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
}

/* The BOM is deliberate: without it Excel opens a UTF-8 CSV as the local codepage and mangles every rupee sign. */
export function toCSV(rows) {
  return "﻿" + rows.map((r) => r.map(csvEscape).join(",")).join("\r\n");
}

export function downloadFile(name, text, mime) {
  const url = URL.createObjectURL(new Blob([text], { type: mime || "text/plain" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    try { document.body.removeChild(a); } catch (e) { /* already gone */ }
    URL.revokeObjectURL(url);
  }, 100);
}

export function slug(s) {
  return (s || "entity").replace(/[^a-z0-9]+/gi, "_").toLowerCase().replace(/^_|_$/g, "");
}

/* Turn an element into a drag-and-drop file target (as the approved dashboard's minutes upload did). */
export function wireDropzone(el, onFiles) {
  if (!el || el._dropWired) return;
  el._dropWired = true;
  const stop = (e) => { e.preventDefault(); e.stopPropagation(); };
  ["dragenter", "dragover"].forEach((ev) => el.addEventListener(ev, (e) => {
    stop(e);
    if (e.dataTransfer) e.dataTransfer.dropEffect = "copy";
    el.classList.add("drag-over");
  }));
  ["dragleave", "dragend"].forEach((ev) => el.addEventListener(ev, (e) => { stop(e); el.classList.remove("drag-over"); }));
  el.addEventListener("drop", (e) => {
    stop(e);
    el.classList.remove("drag-over");
    const files = e.dataTransfer && e.dataTransfer.files;
    if (files && files.length) onFiles(files);
  });
}

export function pillClass(value) {
  const v = String(value || "").toLowerCase();
  if (["met", "completed", "filed", "filed on time", "held", "active", "confirmed", "passed", "yes"].includes(v)) return "pill-ok";
  if (["action_required", "overdue", "not filed", "not yet filed", "rejected", "cancelled", "struck_off", "no"].includes(v)) return "pill-no";
  if (["pending", "planned", "in_progress", "draft", "filed late"].includes(v)) return "pill-part";
  return "pill-na";
}

export function words(s) {
  return String(s == null ? "" : s).replace(/_/g, " ");
}
