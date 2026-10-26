/* The generic table view and record editor. Every table in the database is reachable through these two
   pieces - a list (search, sort, archived toggle, export) and a record modal (all fields, related records,
   history, archive / restore) - so nothing in the schema is left without a screen.

   Nothing is ever deleted: "Archive" hides a record from lists (it stays in the database and the audit log)
   and can be undone with "Restore". */

import * as api from "./api.js";
import { canWriteEntity, canWriteCompany, company, entityMeta, state } from "./state.js";
import { $, debounce, esc, fmtDateTime, toast, words } from "./util.js";
import { clearErrors, collect, displayValue, fieldHTML, hydrateFk, sectionsFor, showErrors } from "./form.js";

/* Records that are created by a workflow, not typed in (the server refuses a bare create too). */
const NO_CREATE = new Set(["company", "activity_instance", "task_instance"]);
/* Fields only a workflow action may change - shown read-only. */
const LOCKED = {
  task_instance: new Set(["status", "completed_by", "completed_at"]),
  activity_instance: new Set(["status", "template_id", "created_by", "params", "company_id"]),
  confirmation: new Set(["status", "confirmed_by", "confirmed_at", "requested_by"]),
};

/* ================= modal stack =================
   A record can open a related record, which opens another. Only one dialog is visible at a time: opening
   a child hides its parent; closing the child brings the parent back and refreshes it. */

const stack = [];

export function openModal(html, { onReturn, size = "modal-lg" } = {}) {
  const host = $("#modalHost");
  const el = document.createElement("div");
  el.className = "modal fade rec-modal";
  el.tabIndex = -1;
  el.innerHTML = `<div class="modal-dialog ${size} modal-dialog-scrollable"><div class="modal-content">${html}</div></div>`;
  host.appendChild(el);
  const inst = new window.bootstrap.Modal(el, { backdrop: "static", keyboard: true });
  const entry = { el, inst, onReturn, suspended: false };
  const prev = stack[stack.length - 1];
  stack.push(entry);
  el.addEventListener("hidden.bs.modal", () => {
    if (entry.suspended) return;
    inst.dispose();
    el.remove();
    const i = stack.indexOf(entry);
    if (i >= 0) stack.splice(i, 1);
    const back = stack[stack.length - 1];
    if (back && back.suspended) {
      back.suspended = false;
      back.inst.show();
      if (back.onReturn) back.onReturn();
    }
  });
  if (prev && !prev.suspended) {
    prev.suspended = true;
    prev.el.addEventListener("hidden.bs.modal", () => inst.show(), { once: true });
    prev.inst.hide();
  } else {
    inst.show();
  }
  return entry;
}

export function closeModal(entry) { entry.inst.hide(); }

/* ================= helpers ================= */

function visibleColumns(meta, opts) {
  const names = opts.columns || meta.list;
  const hide = new Set(opts.hideColumns || []);
  return names.map((n) => meta.columns.find((c) => c.name === n)).filter((c) => c && !hide.has(c.name));
}

function editableRow(key, row) {
  const meta = entityMeta(key);
  if (!canWriteEntity(key)) return false;
  if (meta.write_mode === "company") {
    const cid = row && row.company_id != null ? row.company_id : state.companyId;
    if (cid == null) return false;
    const level = state.user.access[String(cid)];
    return level === "write" || level === "admin";
  }
  return true;
}

function companyDefaults(key, extra) {
  const meta = entityMeta(key);
  const d = { ...(extra || {}) };
  if (state.companyId != null && meta.columns.some((c) => c.name === "company_id") && d.company_id == null) d.company_id = state.companyId;
  if (state.fy && meta.columns.some((c) => c.name === "financial_year") && d.financial_year == null) d.financial_year = state.fy;
  return d;
}

/* ================= list ================= */

export function mountList(container, key, opts = {}) {
  const meta = entityMeta(key);
  const ls = { q: "", archived: false, sort: null, desc: false, page: 1, size: opts.size || 25, total: 0 };
  const cols = visibleColumns(meta, opts);
  const companyId = opts.companyId !== undefined ? opts.companyId : (meta.company_scoped ? state.companyId : null);
  const canAdd = opts.canAdd !== undefined ? opts.canAdd : (canWriteEntity(key) && !NO_CREATE.has(key));
  let rows = [];

  container.innerHTML = `
    ${opts.noToolbar ? "" : `<div class="list-bar no-print">
      <div class="left">
        ${meta.searchable && !opts.externalSearch ? `<input class="form-control form-control-sm" data-l="q" placeholder="Search…" style="min-width:200px">` : ""}
        ${meta.archivable ? `<div class="form-check"><input class="form-check-input" type="checkbox" data-l="archived" id="arch_${esc(key)}_${Math.random().toString(36).slice(2, 6)}"><label class="form-check-label">Show archived</label></div>` : ""}
      </div>
      <div class="right">
        <button class="btn btn-sm btn-outline-brand" data-l="export" type="button">Export CSV</button>
        ${canAdd ? `<button class="btn btn-sm btn-brand" data-l="add" type="button">+ Add ${esc(meta.singular.toLowerCase())}</button>` : ""}
      </div></div>`}
    <div class="tbl-card"><div class="table-responsive">
      <table class="table chk-table data-table align-middle mb-0"><thead><tr>
        ${cols.map((c) => `<th class="${c.fk || c.lookup ? "" : "sortable"}" data-sort="${esc(c.name)}">${esc(c.label)}<span class="sort-ind"></span></th>`).join("")}
      </tr></thead><tbody data-l="body"><tr><td colspan="${cols.length}" class="text-center text-muted py-4">Loading…</td></tr></tbody></table>
    </div><div class="pager" data-l="pager"></div></div>`;

  const q = (s) => container.querySelector(`[data-l="${s}"]`);

  function params() {
    const p = { page: ls.page, size: ls.size, sort: ls.sort || undefined, desc: ls.desc ? "true" : undefined };
    if (ls.q) p.q = ls.q;
    if (ls.archived) p.archived = "true";
    if (companyId != null && meta.company_scoped) p.company_id = companyId;
    if (meta.fy && state.fy && opts.useFy !== false) p.fy = state.fy;
    Object.entries(opts.filters || {}).forEach(([k, v]) => { p["f_" + k] = v; });
    return p;
  }

  async function load() {
    try {
      const data = await api.listEntity(key, params());
      rows = data.rows;
      ls.total = data.total;
      draw();
    } catch (e) {
      q("body").innerHTML = `<tr><td colspan="${cols.length}" class="text-danger p-3">${esc(e.message)}</td></tr>`;
    }
  }

  function draw() {
    const body = q("body");
    if (!rows.length) {
      body.innerHTML = `<tr><td colspan="${cols.length}" class="text-center text-muted py-4">${esc(opts.emptyText || "No records.")}</td></tr>`;
    } else {
      body.innerHTML = rows.map((r) => `<tr data-pk="${esc(r._pk)}" class="${r.is_archived ? "row-archived" : ""}">
        ${cols.map((c) => `<td class="${["decimal", "int"].includes(c.kind) && !c.fk ? "num" : (["text", "textarea"].includes(c.kind) ? "cell-wrap" : "")}">${displayValue(c, r)}</td>`).join("")}</tr>`).join("");
    }
    const pages = Math.max(1, Math.ceil(ls.total / ls.size));
    q("pager").innerHTML = `<span>${ls.total} record${ls.total === 1 ? "" : "s"}</span>
      <span>${pages > 1 ? `<button class="btn btn-sm btn-link p-0 me-2" data-l="prev" ${ls.page <= 1 ? "disabled" : ""}>&larr; Prev</button>
        Page ${ls.page} of ${pages}
        <button class="btn btn-sm btn-link p-0 ms-2" data-l="next" ${ls.page >= pages ? "disabled" : ""}>Next &rarr;</button>` : ""}</span>`;
    container.querySelectorAll("th[data-sort] .sort-ind").forEach((s) => { s.textContent = ""; });
    if (ls.sort) {
      const th = container.querySelector(`th[data-sort="${CSS.escape(ls.sort)}"] .sort-ind`);
      if (th) th.textContent = ls.desc ? " ▼" : " ▲";
    }
  }

  function open(pk) {
    openRecord(key, pk, { onSaved: load, defaults: opts.defaults, fixed: opts.fixed, labels: opts.labels, companyId });
  }

  container.addEventListener("click", (e) => {
    const tr = e.target.closest("tr[data-pk]");
    if (tr) { open(tr.dataset.pk); return; }
    const th = e.target.closest("th.sortable");
    if (th) {
      ls.desc = ls.sort === th.dataset.sort ? !ls.desc : false;
      ls.sort = th.dataset.sort;
      ls.page = 1;
      load();
      return;
    }
    const act = e.target.closest("[data-l]");
    if (!act) return;
    const a = act.dataset.l;
    if (a === "add") openRecord(key, null, { onSaved: load, defaults: opts.defaults, fixed: opts.fixed, labels: opts.labels, companyId });
    else if (a === "prev") { ls.page = Math.max(1, ls.page - 1); load(); }
    else if (a === "next") { ls.page += 1; load(); }
    else if (a === "export") {
      const p = params();
      api.download(`/entities/${key}/export.csv`, { company_id: p.company_id, fy: p.fy, q: p.q, ...Object.fromEntries(Object.entries(p).filter(([k]) => k.startsWith("f_"))) }, `${key}.csv`)
        .catch((err) => toast(err.message));
    }
  });
  const qBox = q("q");
  if (qBox) qBox.addEventListener("input", debounce(() => { ls.q = qBox.value.trim(); ls.page = 1; load(); }, 300));
  const archBox = q("archived");
  if (archBox) archBox.addEventListener("change", () => { ls.archived = archBox.checked; ls.page = 1; load(); });

  const ctl = {
    reload: load,
    setQuery(v) { ls.q = v; ls.page = 1; load(); },
    get total() { return ls.total; },
  };
  load();
  return ctl;
}

/* ================= record editor ================= */

const EXTRA_ACTIONS = {
  document: (row) => (row && row.storage_path
    ? [{ label: "Download file", run: () => api.download(`/documents/${row.id}/download`, {}, row.filename).catch((e) => toast(e.message)) }]
    : []),
  app_user: (row) => (state.user.is_admin && row ? [{ label: "Set password", run: () => passwordModal(row) }] : []),
};

function passwordModal(user) {
  const entry = openModal(`
    <div class="modal-header"><h5 class="modal-title">Set password — ${esc(user.name)}</h5>
      <button type="button" class="btn-close" data-close></button></div>
    <div class="modal-body">
      <label class="form-label">New password (at least 8 characters)</label>
      <input type="password" class="form-control" id="pw1" autocomplete="new-password">
      <div class="text-danger small mt-2" id="pwErr"></div>
    </div>
    <div class="modal-footer"><button class="btn btn-outline-secondary" data-close>Cancel</button>
      <button class="btn btn-brand" id="pwSave">Set password</button></div>`, { size: "" });
  entry.el.addEventListener("click", (e) => { if (e.target.closest("[data-close]")) closeModal(entry); });
  entry.el.querySelector("#pwSave").addEventListener("click", async () => {
    try {
      await api.post(`/admin/users/${user.id}/password`, { new_password: entry.el.querySelector("#pw1").value });
      toast(`Password set for ${user.email}`);
      closeModal(entry);
    } catch (e) { entry.el.querySelector("#pwErr").textContent = e.message; }
  });
}

export async function openRecord(key, pk, opts = {}) {
  const meta = entityMeta(key);
  if (!meta) { toast("Unknown record type"); return; }
  let row = null;
  try {
    if (pk != null) row = (await api.getRecord(key, pk)).row;
  } catch (e) { toast(e.message); return; }
  const creating = row == null;
  // how this record reads as a sentence ("Prashant Joshi (12340012)") - shown under the title
  let recLabel = null;
  if (row && meta.pk.includes("id")) {
    try { recLabel = ((await api.getOptions(key, { ids: row.id })).options[0] || {}).label || null; } catch (e) { /* optional */ }
  }
  const defaults = creating ? companyDefaults(key, opts.defaults) : null;
  const companyName = company() ? company().name : null;
  const labels = { ...(opts.labels || {}), ...(row ? row._labels : {}) };
  if (companyName && defaults && defaults.company_id === state.companyId) labels.company_id = companyName;
  const fixed = new Set([...(opts.fixed || []), ...(meta.columns.some((c) => c.name === "company_id") ? ["company_id"] : []),
    ...Array.from(LOCKED[key] || [])]);
  const editable = editableRow(key, row) && !(row && row.is_archived);
  const title = creating ? `New ${meta.singular.toLowerCase()}` : meta.singular;

  const entry = openModal(`
    <div class="modal-header">
      <div><div class="rec-title" data-r="title">${esc(title)}</div>
        <div class="small text-muted" data-r="sub"></div></div>
      <button type="button" class="btn-close" data-close aria-label="Close"></button>
    </div>
    <div class="modal-body">
      <div class="rec-tabs" data-r="tabs"></div>
      <div data-r="error"></div>
      <div data-r="pane-details"></div>
      <div data-r="pane-related" class="d-none"></div>
      <div data-r="pane-history" class="d-none"></div>
    </div>
    <div class="modal-footer justify-content-between">
      <div data-r="left"></div>
      <div><button class="btn btn-outline-secondary" data-close>Close</button>
        <span data-r="extra"></span><button class="btn btn-brand ${editable ? "" : "d-none"}" data-r="save">${creating ? "Create" : "Save changes"}</button></div>
    </div>`, { onReturn: () => refreshChildren() });

  const $r = (n) => entry.el.querySelector(`[data-r="${n}"]`);
  let historyLoaded = false;
  const childCtl = [];

  function renderDetails(source, message) {
    const secs = sectionsFor(meta);
    const rec = source || {};
    $r("pane-details").innerHTML = (message ? `<div class="rec-note mb-3">${esc(message)}</div>` : "")
      + secs.map((s) => `<div class="rec-section"><h4>${esc(s.title)}</h4><div class="rec-grid">${
        s.cols.map((c) => {
          const ro = !editable || !c.writable;
          return fieldHTML(key, c, { ...rec, _labels: { ...labels, ...(rec._labels || {}) } }, {
            readonly: ro, fixed: fixed.has(c.name) || (!c.writable && c.kind !== "bytea"), labels });
        }).join("")}</div></div>`).join("")
      + (!creating ? `<div class="rec-section"><h4>Record information</h4><div class="rec-sys">
          <div>Created <b>${esc(fmtDateTime(rec.created_at))}</b></div>
          <div>Last changed <b>${esc(fmtDateTime(rec.updated_at))}</b></div>
          ${rec.is_archived ? `<div>Archived <b>${esc(fmtDateTime(rec.archived_at))}</b></div>` : ""}
          <div>Record <b>#${esc(rec._pk)}</b></div></div></div>` : "");
    hydrateFk($r("pane-details"), opts.companyId !== undefined ? opts.companyId : state.companyId);
  }

  function renderTabs(active) {
    const tabs = [["details", "Details"]];
    if (!creating && meta.children.length) tabs.push(["related", "Related records"]);
    if (!creating) tabs.push(["history", "History"]);
    $r("tabs").innerHTML = tabs.map(([id, label]) => `<button type="button" class="rec-tab ${id === active ? "active" : ""}" data-tab="${id}">${label}</button>`).join("");
    ["details", "related", "history"].forEach((id) => $r("pane-" + id).classList.toggle("d-none", id !== active));
    $r("tabs").classList.toggle("d-none", tabs.length < 2);
    if (active === "related") renderChildren();
    if (active === "history" && !historyLoaded) loadHistory();
  }

  function renderChildren() {
    const pane = $r("pane-related");
    pane.innerHTML = meta.children.map((c, i) => {
      const cm = entityMeta(c.entity);
      return cm ? `<div class="child-block"><div class="child-head"><span class="child-title">${esc(c.label)}</span></div><div data-child="${i}"></div></div>` : "";
    }).join("");
    childCtl.length = 0;
    meta.children.forEach((c, i) => {
      const cm = entityMeta(c.entity);
      const host = pane.querySelector(`[data-child="${i}"]`);
      if (!cm || !host) return;
      const defaults = { [c.fk]: row.id };
      if (cm.columns.some((x) => x.name === "company_id") && row.company_id != null) defaults.company_id = row.company_id;
      childCtl.push(mountList(host, c.entity, {
        filters: { [c.fk]: row.id }, hideColumns: [c.fk], size: 10, defaults, fixed: [c.fk],
        labels: { [c.fk]: parentLabel() }, companyId: row.company_id != null ? row.company_id : state.companyId,
        useFy: false, canAdd: editable && canWriteEntity(c.entity) && !NO_CREATE.has(c.entity),
        emptyText: "None recorded.", noToolbar: !(cm.archivable),
      }));
    });
  }

  function parentLabel() {
    return recLabel || `${meta.singular} #${row ? row.id : ""}`;
  }

  function refreshChildren() { childCtl.forEach((c) => c.reload()); }

  async function loadHistory() {
    historyLoaded = true;
    const pane = $r("pane-history");
    pane.innerHTML = `<div class="text-muted">Loading…</div>`;
    try {
      const { entries } = await api.recordHistory(key, pk);
      pane.innerHTML = entries.length ? entries.map((en) => `<div class="hist-item hist-op-${esc(en.operation)}">
          <div><b>${esc(en.operation === "INSERT" ? "Created" : "Changed")}</b> by ${esc(en.actor)}
            <span class="when">· ${esc(fmtDateTime(en.at))}</span></div>
          <div class="chg">${Object.entries(en.changes).filter(([k, v]) => !["created_at", "updated_at", "id", "is_archived"].includes(k)
              && (en.operation !== "INSERT" || (v.to != null && v.to !== false))).slice(0, 14).map(([k, v]) =>
            en.operation === "INSERT"
              ? `<code>${esc(k)}</code> ${esc(fmtVal(v.to))}`
              : `<code>${esc(k)}</code> ${esc(fmtVal(v.from))} &rarr; <b>${esc(fmtVal(v.to))}</b>`).join(" &nbsp;·&nbsp; ") || "No field changes"}</div>
        </div>`).join("") : `<div class="text-muted">No history recorded.</div>`;
    } catch (e) { pane.innerHTML = `<div class="text-danger">${esc(e.message)}</div>`; }
  }

  function fmtVal(v) { return v == null ? "—" : typeof v === "object" ? JSON.stringify(v) : String(v); }

  function setHeader() {
    $r("sub").textContent = row
      ? `${recLabel ? recLabel + " · " : ""}Record #${row._pk}${row.is_archived ? " · archived" : ""}`
      : "Fill in the fields and press Create.";
    const left = $r("left");
    left.innerHTML = "";
    if (row && meta.archivable && editable !== false && editableRow(key, row)) {
      left.innerHTML = row.is_archived
        ? `<button class="btn btn-outline-secondary" data-r="restore">Restore</button>`
        : `<button class="btn btn-outline-danger" data-r="archive">Archive</button>`;
    }
    const extra = $r("extra");
    extra.innerHTML = "";
    (EXTRA_ACTIONS[key] ? EXTRA_ACTIONS[key](row) : []).forEach((a, i) => {
      const b = document.createElement("button");
      b.className = "btn btn-outline-brand me-2";
      b.textContent = a.label;
      b.addEventListener("click", a.run);
      extra.appendChild(b);
    });
  }

  renderDetails(creating ? { ...defaults, _labels: labels } : row);
  renderTabs("details");
  setHeader();

  entry.el.addEventListener("click", async (e) => {
    if (e.target.closest("[data-close]")) { closeModal(entry); return; }
    const tab = e.target.closest("[data-tab]");
    if (tab) { renderTabs(tab.dataset.tab); return; }
    if (e.target.closest('[data-r="save"]')) { save(); return; }
    if (e.target.closest('[data-r="archive"]')) {
      if (!window.confirm(`Archive this ${meta.singular.toLowerCase()}? It will be hidden from lists but kept in the database and the audit log. You can restore it later.`)) return;
      try { await api.archiveRecord(key, pk); toast("Archived"); closeModal(entry); if (opts.onSaved) opts.onSaved(); }
      catch (err) { $r("error").innerHTML = `<div class="rec-error">${esc(err.message)}</div>`; }
      return;
    }
    if (e.target.closest('[data-r="restore"]')) {
      try { await api.restoreRecord(key, pk); toast("Restored"); closeModal(entry); if (opts.onSaved) opts.onSaved(); }
      catch (err) { $r("error").innerHTML = `<div class="rec-error">${esc(err.message)}</div>`; }
    }
  });

  async function save() {
    const root = $r("pane-details");
    clearErrors(root);
    $r("error").innerHTML = "";
    const btn = $r("save");
    btn.disabled = true;
    try {
      if (creating) {
        const payload = Object.fromEntries(Object.entries(collect(root, null)).filter(([, v]) => v !== null && v !== ""));
        const created = (await api.createRecord(key, payload)).row;
        toast(`${meta.singular} created`);
        if (opts.onSaved) opts.onSaved();
        if (meta.children.length) {
          // keep the dialog open on the new record so related records can be added straight away
          closeModal(entry);
          setTimeout(() => openRecord(key, created._pk, opts), 350);
        } else closeModal(entry);
      } else {
        const payload = collect(root, row);
        if (!Object.keys(payload).length) { toast("Nothing changed"); btn.disabled = false; return; }
        payload.updated_at = row.updated_at;
        row = (await api.updateRecord(key, pk, payload)).row;
        toast("Saved");
        renderDetails(row);
        setHeader();
        if (opts.onSaved) opts.onSaved();
      }
    } catch (err) {
      $r("error").innerHTML = `<div class="rec-error">${esc(err.message)}</div>`;
      showErrors(root, err.fields);
      if (err.code === "stale") $r("error").innerHTML += `<div class="rec-note mt-2">Close this dialog and open the record again to see the latest values.</div>`;
    } finally { btn.disabled = false; }
  }
}

/* ================= a full page for one table ================= */

export function renderEntityPage(key) {
  const meta = entityMeta(key);
  if (!meta) { $("#view").innerHTML = `<div class="tbl-card p-4 text-muted">Not available.</div>`; return null; }
  const co = company();
  $("#crumb").innerHTML = "";
  $("#pageTitle").textContent = meta.label;
  const bits = [];
  if (meta.company_scoped && co) bits.push(esc(co.name));
  if (meta.fy && state.fy) bits.push(`FY ${esc(state.fy)} <span class="text-muted">(change in the sidebar)</span>`);
  if (!meta.can_write) bits.push("read only");
  $("#pageSub").innerHTML = bits.join(" &middot; ") || "&nbsp;";
  if (meta.company_scoped && !co) {
    $("#view").innerHTML = `<div class="tbl-card p-5 text-center text-muted">Open a company to see its ${esc(meta.label.toLowerCase())}.</div>`;
    return null;
  }
  $("#view").innerHTML = `<div id="entityHost"></div>`;
  const ctl = mountList($("#entityHost"), key, { externalSearch: true });
  return ctl;
}
