/* Field engine: draws the right control for any database column and reads the values back.

   Everything is driven by the column's metadata (kind, required, dropdown list, allowed choices, the table it
   points at), which the server reads from the live database - so a field added to the schema appears on the
   forms without changing this file. */

import * as api from "./api.js";
import { state, entityMeta, lookup } from "./state.js";
import { esc, fmtDate, fmtDateTime, fmtNumber, fmtTime, pillClass, toLocalInput, words } from "./util.js";

/* ---------- read-only display of a value (list cells, read-only fields) ---------- */

export function displayValue(col, row) {
  const v = row[col.name];
  if (col.secret) return v ? '<span class="pill pill-na">stored (encrypted)</span>' : '<span class="muted-dash">—</span>';
  if (v == null || v === "") return '<span class="muted-dash">—</span>';
  if (col.fk || col.lookup) {
    const label = (row._labels && row._labels[col.name])
      || (col.lookup ? (lookup(col.lookup).find((x) => x.id === v) || {}).label : null);
    return `<span class="fk-chip">${esc(label || "#" + v)}</span>`;
  }
  if (col.kind === "bool") return `<span class="pill ${v ? "pill-ok" : "pill-na"}">${v ? "Yes" : "No"}</span>`;
  if (col.kind === "date") return esc(fmtDate(v));
  if (col.kind === "time") return esc(fmtTime(v));
  if (col.kind === "datetime") return esc(fmtDateTime(v));
  if (col.kind === "decimal") return esc(fmtNumber(v, col.scale));
  if (col.kind === "int") return esc(fmtNumber(v, 0));
  if (col.kind === "json") return `<code>${esc(JSON.stringify(v).slice(0, 80))}</code>`;
  if (col.kind === "vector") return `<span class="pill pill-na">${esc(v)}-dimension vector</span>`;
  if (col.choices) return `<span class="pill ${pillClass(v)}">${esc(words(v))}</span>`;
  return esc(v);
}

/* ---------- editable controls ---------- */

const ph = (col) => (col.format === "financial_year" ? ' placeholder="2024-25"' : "");

function optionTags(list, selected, blank) {
  const none = blank ? `<option value="">—</option>` : "";
  return none + list.map((o) =>
    `<option value="${esc(o.value)}" ${String(o.value) === String(selected) ? "selected" : ""}>${esc(o.label)}</option>`).join("");
}

export function control(entityKey, col, value, opts = {}) {
  const id = `f_${entityKey}_${col.name}`;
  const base = `id="${id}" data-f="${esc(col.name)}" data-kind="${esc(col.kind)}"`;
  const disabled = opts.readonly ? " disabled" : "";
  const blank = !col.required;
  if (col.kind === "bytea") {
    if (!col.secret_enabled) {
      return `<input class="form-control form-control-sm" disabled value="Storage switched off by policy">`;
    }
    return `<input type="password" class="form-control form-control-sm" ${base} autocomplete="new-password"
      placeholder="${value ? "A value is stored — type to replace it" : "Not set"}"${disabled}>`;
  }
  if (col.kind === "vector") {
    return `<textarea class="form-control form-control-sm" ${base} rows="2" spellcheck="false"
      placeholder="${value ? `A ${esc(value)}-number vector is stored. Paste a JSON array to replace it.` : `JSON array of ${esc(col.dims || "")} numbers`}"${disabled}></textarea>`;
  }
  if (col.lookup) {
    const list = lookup(col.lookup).map((x) => ({ value: x.id, label: x.label }));
    return `<select class="form-select form-select-sm" ${base}${disabled}>${optionTags(list, value, blank)}</select>`;
  }
  if (col.fk) {
    return `<select class="form-select form-select-sm" ${base} data-fk="${esc(col.fk)}" data-selected="${esc(value == null ? "" : value)}"${disabled}>
      ${value != null ? `<option value="${esc(value)}" selected>#${esc(value)}</option>` : '<option value="">—</option>'}</select>`;
  }
  if (col.choices) {
    const list = col.choices.map((c) => ({ value: c, label: words(c) }));
    return `<select class="form-select form-select-sm" ${base}${disabled}>${optionTags(list, value, blank)}</select>`;
  }
  if (col.kind === "bool") {
    if (col.nullable === false) {          // a yes/no that can never be empty is a checkbox
      return `<div class="form-check"><input class="form-check-input" type="checkbox" ${base} ${value ? "checked" : ""}${disabled}></div>`;
    }
    const sel = value == null ? "" : value ? "true" : "false";
    return `<select class="form-select form-select-sm" ${base}${disabled}>${optionTags(
      [{ value: "true", label: "Yes" }, { value: "false", label: "No" }], sel, true)}</select>`;
  }
  if (col.kind === "textarea") {
    return `<textarea class="form-control form-control-sm" ${base} rows="3"${disabled}>${esc(value == null ? "" : value)}</textarea>`;
  }
  if (col.kind === "json") {
    const text = value == null ? "" : typeof value === "string" ? value : JSON.stringify(value, null, 2);
    return `<textarea class="form-control form-control-sm" ${base} rows="4" spellcheck="false" style="font-family:ui-monospace,Consolas,monospace"${disabled}>${esc(text)}</textarea>`;
  }
  if (col.kind === "date") {
    return `<input type="date" class="form-control form-control-sm" ${base} value="${esc(value || "")}"${disabled}>`;
  }
  if (col.kind === "time") {
    return `<input type="time" class="form-control form-control-sm" ${base} value="${esc(fmtTime(value))}"${disabled}>`;
  }
  if (col.kind === "datetime") {
    return `<input type="datetime-local" class="form-control form-control-sm" ${base} value="${esc(toLocalInput(value))}"${disabled}>`;
  }
  if (col.kind === "int") {
    return `<input type="number" step="1" class="form-control form-control-sm" ${base} value="${esc(value == null ? "" : value)}"${disabled}>`;
  }
  if (col.kind === "decimal") {
    const step = col.scale ? (1 / Math.pow(10, col.scale)).toFixed(col.scale) : "any";
    return `<input type="number" step="${step}" class="form-control form-control-sm" ${base} value="${esc(value == null ? "" : value)}"${disabled}>`;
  }
  return `<input type="text" class="form-control form-control-sm" ${base} value="${esc(value == null ? "" : value)}"${ph(col)}${disabled}>`;
}

export function fieldHTML(entityKey, col, row, opts = {}) {
  const value = row ? row[col.name] : null;
  const wide = ["textarea", "json", "vector"].includes(col.kind) ? " wide" : "";
  const star = col.required && !opts.readonly ? ' <span class="req">*</span>' : "";
  const help = col.help ? `<div class="help">${esc(col.help)}</div>` : "";
  let body;
  if (opts.fixed) {
    body = `<div class="ro">${displayValue(col, row || { [col.name]: value, _labels: opts.labels || {} })}</div>
            <input type="hidden" data-f="${esc(col.name)}" data-kind="${esc(col.kind)}" value="${esc(value)}">`;
  } else if (opts.readonly && !col.fk && !col.lookup && col.kind !== "bool" && !col.choices) {
    body = `<div class="ro">${displayValue(col, row || {})}</div>`;
  } else {
    body = control(entityKey, col, value, opts);
  }
  return `<div class="rec-field${wide}" data-field="${esc(col.name)}">
    <label for="f_${esc(entityKey)}_${esc(col.name)}">${esc(col.label)}${star}</label>${body}${help}
    <div class="err"></div></div>`;
}

/* ---------- filling the dropdowns that point at other tables ---------- */

/** Replace each <select data-fk> with the options the server offers (scoped to what the user may see). */
export async function hydrateFk(root, companyId) {
  const selects = Array.from(root.querySelectorAll("select[data-fk]"));
  await Promise.all(selects.map(async (sel) => {
    const entity = sel.dataset.fk;
    const meta = entityMeta(entity);
    if (!meta) return;
    const selected = sel.dataset.selected;
    const params = { limit: 200 };
    // dropdowns of records that belong to one company are limited to the open company; shared people lists are not
    if (companyId && meta.scope !== "masters" && meta.scope !== "global" && meta.scope !== "admin" && entity !== "app_user") {
      params.company_id = companyId;
    }
    try {
      const { options } = await api.getOptions(entity, params);
      const have = new Set(options.map((o) => String(o.id)));
      let extra = "";
      if (selected && !have.has(selected)) {
        const one = await api.getOptions(entity, { ids: selected });
        const hit = (one.options || [])[0];
        extra = `<option value="${esc(selected)}" selected>${esc(hit ? hit.label : "#" + selected)}</option>`;
      }
      const blank = !sel.closest(".rec-field") || !sel.closest(".rec-field").querySelector("label .req");
      sel.innerHTML = (blank ? `<option value="">—</option>` : `<option value="">Select…</option>`) + extra
        + options.map((o) => `<option value="${esc(o.id)}" ${String(o.id) === selected ? "selected" : ""}>${esc(o.label)}</option>`).join("");
    } catch (e) { /* leave the placeholder option; the server will still validate on save */ }
  }));
}

/* ---------- reading values back ---------- */

function readControl(el) {
  const kind = el.dataset.kind;
  if (el.type === "checkbox") return el.checked;
  const raw = el.value;
  if (raw === "" || raw == null) return null;
  if (el.tagName === "SELECT" && (kind === "bool")) return raw === "true";
  if (el.tagName === "SELECT" && (kind === "int" || el.dataset.fk)) return Number(raw);
  if (kind === "int") return Number(raw);
  if (kind === "decimal") return raw;                 // keep as typed; the server keeps it exact
  if (kind === "datetime") return raw;                // local India time, no zone: the server treats it as IST
  return raw;
}

/** Collect the form's values. With `original` (the loaded row) only fields that changed are returned. */
export function collect(root, original) {
  const out = {};
  root.querySelectorAll("[data-f]").forEach((el) => {
    if (el.disabled || el.type === "hidden" && original) return;
    const name = el.dataset.f;
    const value = readControl(el);
    if (el.dataset.kind === "bytea" && value == null) return;      // blank secret = leave unchanged
    if (el.dataset.kind === "vector" && value == null) return;
    if (original) {
      const before = original[name];
      const same = (before == null && value == null)
        || (before != null && value != null && normalise(before, el.dataset.kind) === normalise(value, el.dataset.kind));
      if (same) return;
    }
    out[name] = value;
  });
  return out;
}

function normalise(v, kind) {
  if (kind === "decimal") return Number(v);
  if (kind === "json") { try { return JSON.stringify(typeof v === "string" ? JSON.parse(v) : v); } catch (e) { return String(v); } }
  if (kind === "datetime") return new Date(v).getTime();
  if (kind === "time") return String(v).slice(0, 5);
  return String(v);
}

/* ---------- validation messages from the server ---------- */

export function clearErrors(root) {
  root.querySelectorAll(".rec-field.has-error").forEach((f) => f.classList.remove("has-error"));
  root.querySelectorAll(".rec-field .err").forEach((e) => { e.textContent = ""; });
}

export function showErrors(root, fields) {
  let first = null;
  Object.entries(fields || {}).forEach(([name, message]) => {
    const wrap = root.querySelector(`.rec-field[data-field="${CSS.escape(name)}"]`);
    if (!wrap) return;
    wrap.classList.add("has-error");
    wrap.querySelector(".err").textContent = message;
    first = first || wrap;
  });
  if (first) first.scrollIntoView({ block: "center", behavior: "smooth" });
}

/* ---------- grouping a table's fields into sections ---------- */

const SKIP_IN_FORM = new Set(["id", "created_at", "updated_at", "is_archived", "archived_at", "archived_by"]);

export function sectionsFor(meta, { includeReadonly = true } = {}) {
  const cols = meta.columns.filter((c) => !SKIP_IN_FORM.has(c.name) && (includeReadonly || c.writable));
  const byName = Object.fromEntries(cols.map((c) => [c.name, c]));
  const used = new Set();
  const sections = [];
  (meta.sections || []).forEach((s) => {
    const list = s.columns.map((n) => byName[n]).filter(Boolean);
    list.forEach((c) => used.add(c.name));
    if (list.length) sections.push({ title: s.title, cols: list });
  });
  const rest = cols.filter((c) => !used.has(c.name));
  if (!sections.length) {
    const groups = [
      ["Details", (c) => !["date", "time", "datetime", "bool", "decimal"].includes(c.kind) || c.fk || c.lookup],
      ["Dates and times", (c) => ["date", "time", "datetime"].includes(c.kind)],
      ["Amounts and numbers", (c) => c.kind === "decimal"],
      ["Flags", (c) => c.kind === "bool" && !c.fk],
    ];
    const left = new Set(rest.map((c) => c.name));
    groups.forEach(([title, test]) => {
      const list = rest.filter((c) => left.has(c.name) && test(c));
      list.forEach((c) => left.delete(c.name));
      if (list.length) sections.push({ title, cols: list });
    });
  } else if (rest.length) {
    sections.push({ title: "Other details", cols: rest });
  }
  return sections;
}
