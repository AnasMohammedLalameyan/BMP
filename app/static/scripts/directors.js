/* Directors - everything about the board of one company in one panel.

   A person is entered once; each time they serve is a separate stint, so a director who resigned and was re-appointed shows two rows,
   and a change of designation is a new designation row, never an overwrite. The Register tab is the default; the other tabs hold the
   records that used to be separate sidebar entries (person and KYC, appointments, committees, declarations). */

import * as api from "./api.js";
import { canWriteCompany, company, entityMeta, lookup, state } from "./state.js";
import { $, ceasedInFy, directorShown, esc, fmtDate, fmtDateDMY, showHistorical, toast } from "./util.js";
import { clearErrors, collect, fieldHTML, hydrateFk, showErrors } from "./form.js";
import { closeModal, mountList, openModal, openRecord } from "./entity.js";
import { mountTabs } from "./tabs.js";

let historical = showHistorical();         // "Show Historical/Ceased Directors" - off by default, remembered for the session
let segment = "all";
let rows = [];

const FLAGS = [["is_independent", "Independent"], ["is_whole_time", "Whole-time"], ["is_nominee", "Nominee"],
  ["is_additional", "Additional"], ["is_alternate", "Alternate"], ["is_signatory", "Signatory"],
  ["retires_by_rotation", "Retires by rotation"]];

/* Key managerial personnel: the designations the law treats as KMP (there is no KMP flag in the data model). */
const KMP = new Set(["MD", "CMD", "CWMD", "WTD", "CEO", "CFO", "CS", "MANAGER"]);

const SEGMENTS = [
  ["all", () => "All", () => true],
  ["active", (fy) => (fy ? `Active in FY ${fy}` : "Active"), (r, fy) => directorShown(r, fy)],
  ["ceased", () => "Ceased", (r) => !r.is_current],
  ["independent", () => "Independent", (r) => r.is_independent],
  ["kmp", () => "KMP", (r) => KMP.has(r.designation_code)],
  ["committee", () => "On a committee", (r) => r.on_committee],
];

export async function render() {
  const co = company();
  $("#crumb").textContent = "";
  $("#pageTitle").textContent = "Directors";
  $("#pageSub").innerHTML = `${esc(co ? co.name : "")} &middot; <span class="text-muted">the board over time — a resigned and re-appointed director appears twice</span>`;
  $("#view").innerHTML = `<div class="tbl-card p-4 text-muted">Loading…</div>`;
  try { rows = (await api.get(`/companies/${state.companyId}/directors-register`, { include_ceased: "true", fy: state.fy || undefined })).rows; }
  catch (e) { $("#view").innerHTML = `<div class="tbl-card p-4 text-danger">${esc(e.message)}</div>`; return; }
  mountTabs($("#view"), [
    { id: "register", label: "Register", render: drawRegister },
    { id: "kyc", label: "DIN & KYC", render: (el) => lists(el, [
      ["Persons on this board", "director", "Each person is recorded once, with DIN, PAN and contact details."],
      ["DIR-3 KYC by year", "director_kyc"], ["Residency by year", "director_residency"]]) },
    { id: "appointments", label: "Appointments", render: (el) => lists(el, [
      ["Board stints", "directorship", "Each period of service, with its dates and role flags."],
      ["Designation history", "directorship_role"], ["Independent director terms", "independent_director_term"]]) },
    { id: "resignations", label: "Resignations", render: drawResignations },
    { id: "committees", label: "Board Committees", render: (el) => lists(el, [
      ["Committees", "committee"], ["Committee members", "committee_member"]]) },
    { id: "declarations", label: "Declarations & other directorships", render: (el) => lists(el, [
      ["Declarations", "director_declaration"], ["Other directorships", "director_other_directorship"]]) },
  ], { active: state.tab });
}

/** Stacked lists (the generic list component: search, sort, CSV, archive and the record editor all work). */
function lists(el, sections) {
  el.innerHTML = sections.map(([title, key, note], i) => entityMeta(key)
    ? `<section class="md-card mb-3"><div class="md-h-row"><h3 class="md-h">${esc(title)}</h3></div>
        ${note ? `<div class="md-note text-muted">${esc(note)}</div>` : ""}<div data-list="${i}"></div></section>` : "").join("");
  sections.forEach(([, key], i) => { const host = el.querySelector(`[data-list="${i}"]`); if (host) mountList(host, key, { size: 10 }); });
}

/* ---------- Register ---------- */

function emptyText() {
  if (!rows.length) return "No directors recorded.";
  return state.fy ? `No directors were active in ${state.fy}` : "No current directors.";
}

/** The phone number exactly as stored; a tel: link (digits and + only) lets a phone dial it. */
function phoneHTML(phone) {
  if (!phone) return "—";
  const dial = String(phone).replace(/[^0-9+]/g, "");
  return dial ? `<a href="tel:${esc(dial)}">${esc(phone)}</a>` : esc(phone);
}

function drawRegister(host) {
  const base = historical ? rows : rows.filter((r) => directorShown(r, state.fy));
  const pick = SEGMENTS.find(([id]) => id === segment) || SEGMENTS[0];
  const list = base.filter((r) => pick[2](r, state.fy));
  const hidden = rows.length - base.length;
  const canAdd = canWriteCompany();
  const body = list.map((r) => `<tr class="${r.is_current ? "" : "ceased"}" data-ship="${r.directorship_id}" role="button">
      <td><div class="co-name">${esc(r.full_name)}</div><div class="co-sub">${r.din ? "DIN " + esc(r.din) : "no DIN"}${r.age_years != null ? ` · age ${r.age_years}` : ""}${r.gender ? ` · ${esc(r.gender)}` : ""}</div></td>
      <td>${esc(r.designation || "—")}${r.category ? `<div class="co-sub">${esc(r.category)}</div>` : ""}</td>
      <td>${esc(fmtDate(r.start_date))}</td>
      <td>${r.end_date ? `${esc(fmtDate(r.end_date))}<div class="co-sub">${esc(r.cessation_reason || "")}</div>${ceasedInFy(r.end_date, state.fy) ? `<span class="pill pill-no">Ceased on ${esc(fmtDateDMY(r.end_date))}</span>` : ""}` : '<span class="pill pill-ok">Serving</span>'}</td>
      <td>${FLAGS.filter(([k]) => r[k]).map(([, l]) => `<span class="flag-chip">${l}</span>`).join("") || '<span class="muted-dash">—</span>'}</td>
      <td>${esc(r.email || "—")}${r.dsc_valid_until ? `<div class="co-sub">DSC to ${esc(fmtDate(r.dsc_valid_until))}</div>` : ""}</td>
      <td class="cell-wrap">${esc(r.address || "—")}</td>
      <td class="text-nowrap">${phoneHTML(r.phone)}</td>
      <td class="text-end no-print"><button class="btn btn-sm btn-link p-0" data-person="${r.director_id}" type="button">Person</button></td>
    </tr>`).join("");
  host.innerHTML = `<div class="seg-bar no-print" role="group" aria-label="Filter directors">${SEGMENTS.map(([id, label, test]) =>
      `<button type="button" class="seg-btn ${id === pick[0] ? "active" : ""}" data-seg="${id}" aria-pressed="${id === pick[0]}">${esc(label(state.fy))}<span class="n">${base.filter((r) => test(r, state.fy)).length}</span></button>`).join("")}</div>
    <div class="list-bar no-print">
      <div class="left"><div class="form-check"><input class="form-check-input" type="checkbox" id="showHistorical" ${historical ? "checked" : ""}>
        <label class="form-check-label" for="showHistorical">Show Historical/Ceased Directors</label></div>
        <span class="text-muted small">${list.length} row${list.length === 1 ? "" : "s"}${hidden ? ` &middot; ${hidden} historical hidden` : ""}</span></div>
      <div class="right">${canAdd ? `<button class="btn btn-sm btn-brand" id="addDirector" type="button">+ Add director / KMP</button>` : ""}</div></div>
    <div class="tbl-card"><div class="table-responsive"><table class="table chk-table reg-table align-middle mb-0">
      <thead><tr><th>Name</th><th>Designation</th><th>Appointed</th><th>Ceased</th><th>Role flags</th><th>Contact</th><th>Address</th><th>Phone Number</th><th></th></tr></thead>
      <tbody>${body || `<tr><td colspan="9" class="text-center text-muted py-4">${esc(emptyText())}</td></tr>`}</tbody></table></div></div>
    <div class="text-muted mt-2" style="font-size:.76rem">Click a row to open the board stint (designation history, independent-director terms, declarations,
      committees, remuneration). &ldquo;Person&rdquo; opens the individual's own record (DIN, PAN, birth date, KYC, residency, other directorships).</div>`;
  host.querySelector("#showHistorical").addEventListener("change", (e) => { historical = e.target.checked; showHistorical(historical); drawRegister(host); });
  const add = host.querySelector("#addDirector");
  if (add) add.addEventListener("click", addDialog);
  host.onclick = (e) => {
    if (e.target.closest("a[href^='tel:']")) return;
    const seg = e.target.closest("[data-seg]");
    if (seg) { segment = seg.dataset.seg; drawRegister(host); return; }
    const person = e.target.closest("[data-person]");
    if (person) { openRecord("director", person.dataset.person, { onSaved: render }); return; }
    const tr = e.target.closest("tr[data-ship]");
    if (tr) openRecord("directorship", tr.dataset.ship, { onSaved: render });
  };
}

/* ---------- Resignations: every stint that has an end date ---------- */

function drawResignations(host) {
  const gone = rows.filter((r) => r.end_date).sort((a, b) => String(b.end_date).localeCompare(String(a.end_date)));
  host.innerHTML = `<div class="tbl-card"><div class="table-responsive"><table class="table chk-table align-middle mb-0">
      <thead><tr><th>Name</th><th>Designation</th><th>Appointed</th><th>Resigned / ceased</th><th>Reason</th></tr></thead>
      <tbody>${gone.map((r) => `<tr data-ship="${r.directorship_id}" role="button"><td><div class="co-name">${esc(r.full_name)}</div>
        <div class="co-sub">${r.din ? "DIN " + esc(r.din) : "no DIN"}</div></td><td>${esc(r.designation || "—")}</td><td>${esc(fmtDate(r.start_date))}</td>
        <td>${esc(fmtDate(r.end_date))}</td><td class="cell-wrap">${esc(r.cessation_reason || "—")}</td></tr>`).join("")
        || `<tr><td colspan="5" class="text-center text-muted py-4">No resignations recorded.</td></tr>`}</tbody></table></div></div>
    <div class="text-muted mt-2" style="font-size:.76rem">These are the board stints that have an end date. Click one to open it.</div>`;
  host.onclick = (e) => {
    const tr = e.target.closest("tr[data-ship]");
    if (tr) openRecord("directorship", tr.dataset.ship, { onSaved: render });
  };
}

/* ---------- add a person to the board in one step ---------- */

function addDialog() {
  const dm = entityMeta("director");
  const sm = entityMeta("directorship");
  const personCols = dm.columns.filter((c) => c.writable && c.kind !== "bytea" && !["aadhaar_encrypted"].includes(c.name));
  const shipCols = sm.columns.filter((c) => c.writable && !["company_id", "director_id"].includes(c.name));
  const entry = openModal(`
    <div class="modal-header"><div><div class="rec-title">Add a director / KMP</div>
      <div class="small text-muted">Pick an existing person, or enter a new one. If the DIN is already known the existing person is reused.</div></div>
      <button type="button" class="btn-close" data-close></button></div>
    <div class="modal-body"><div id="dErr"></div>
      <div class="rec-section"><h4>Person</h4>
        <div class="rec-field mb-2"><label>Existing person</label>
          <select class="form-select form-select-sm" id="existing" data-fk="director" data-selected=""><option value="">— enter a new person below —</option></select></div>
        <div id="personFields" class="rec-grid">${personCols.map((c) => fieldHTML("director", c, {}, {})).join("")}</div></div>
      <div class="rec-section"><h4>Board stint</h4><div id="shipFields" class="rec-grid">${shipCols.map((c) => fieldHTML("directorship", c, c.name === "is_board_member" ? { is_board_member: true } : {}, {})).join("")}</div></div>
      <div class="rec-section"><h4>Designation</h4><div class="rec-grid">
        <div class="rec-field"><label>Designation</label><select class="form-select form-select-sm" id="designation">
          <option value="">—</option>${lookup("DESIGNATION").map((d) => `<option value="${d.id}">${esc(d.label)}</option>`).join("")}</select></div>
        <div class="rec-field"><label>Designation start date</label><input type="date" class="form-control form-control-sm" id="designationStart"></div></div></div>
    </div>
    <div class="modal-footer"><button class="btn btn-outline-secondary" data-close>Cancel</button>
      <button class="btn btn-brand" id="dSave">Add to board</button></div>`);
  hydrateFk(entry.el.querySelector("#existing").parentElement, null);
  const existing = entry.el.querySelector("#existing");
  existing.addEventListener("change", () => entry.el.querySelector("#personFields").classList.toggle("d-none", !!existing.value));
  entry.el.addEventListener("click", async (e) => {
    if (e.target.closest("[data-close]")) { closeModal(entry); return; }
    if (!e.target.closest("#dSave")) return;
    const errBox = entry.el.querySelector("#dErr");
    errBox.innerHTML = "";
    clearErrors(entry.el);
    const clean = (o) => Object.fromEntries(Object.entries(o).filter(([, v]) => v !== null && v !== ""));
    const payload = {
      directorship: clean(collect(entry.el.querySelector("#shipFields"), null)),
      designation_id: entry.el.querySelector("#designation").value ? Number(entry.el.querySelector("#designation").value) : null,
      designation_start: entry.el.querySelector("#designationStart").value || null,
    };
    if (existing.value) payload.director_id = Number(existing.value);
    else payload.director = clean(collect(entry.el.querySelector("#personFields"), null));
    try {
      const res = await api.post(`/companies/${state.companyId}/directors-register`, payload);
      toast(res.person_created ? "New person created and added to the board" : "Added to the board");
      closeModal(entry);
      render();
    } catch (err) {
      errBox.innerHTML = `<div class="rec-error">${esc(err.message)}</div>`;
      // field keys from the server are "director.full_name" / "directorship.start_date"; map them onto the form
      const flat = {};
      Object.entries(err.fields || {}).forEach(([k, v]) => { flat[k.split(".").pop()] = v; });
      showErrors(entry.el, flat);
    }
  });
}
