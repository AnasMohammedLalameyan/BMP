/* Activity Log - who changed what, and when (the approved dashboard's append-only log, now backed by the
   database's own audit trail: every insert and update is recorded with the person, the time and the values
   before and after, and nobody can edit or remove an entry). */

import * as api from "./api.js";
import { canWriteCompany, company, state } from "./state.js";
import { $, $$, downloadFile, esc, fmtDateTime, slug, toCSV, toast, words } from "./util.js";

let entries = [];
let offset = 0;
let more = false;

export async function render() {
  const co = company();
  $("#crumb").innerHTML = "<a class='crumb-link' data-view='overview' role='button' title='Back to the Dashboard Overview'>Working Papers</a> <span class='sep'>/</span> Activity Log";
  $("#pageTitle").textContent = "Activity Log";
  $("#pageSub").innerHTML = `${esc(co ? co.name : "")} &middot; <span class="text-muted">who changed what, and when — append-only</span>`;
  entries = []; offset = 0;
  $("#view").innerHTML = `<div class="tbl-card">
    <div class="d-flex justify-content-between align-items-center p-3 pb-2 flex-wrap gap-2">
      <div class="fw-bold text-brand">Activity log <span class="text-muted fw-normal" id="logCount"></span></div>
      <button class="btn btn-sm btn-outline-brand" id="logExport" type="button">Export CSV</button></div>
    <div class="px-3 text-muted small pb-2">Every change is stamped with the signed-in person. Entries cannot be edited or removed; an edit adds a new entry.</div>
    <div class="px-3"><input class="form-control form-control-sm" id="logSearch" placeholder="Filter by user / record type / action…"></div>
    <div class="table-responsive mt-2"><table class="table table-sm wp-tbl mb-0">
      <thead><tr><th style="width:165px">Timestamp</th><th style="width:150px">User</th><th>Action</th><th>What changed</th></tr></thead>
      <tbody id="logBody"><tr><td colspan="4" class="text-center text-muted py-4">Loading…</td></tr></tbody></table></div>
    <div class="pager"><span id="logInfo"></span><span><button class="btn btn-sm btn-link p-0" id="logMore" type="button" style="display:none">Load older entries</button></span></div></div>`;
  $("#logSearch").addEventListener("input", filter);
  $("#logExport").addEventListener("click", exportCsv);
  $("#logMore").addEventListener("click", () => load(true));
  load(false);
}

async function load(append) {
  try {
    const res = await api.get("/audit", { company_id: state.companyId, limit: 100, offset: append ? offset : 0 });
    entries = append ? entries.concat(res.entries) : res.entries;
    offset = entries.length;
    more = res.has_more;
    draw();
  } catch (e) { $("#logBody").innerHTML = `<tr><td colspan="4" class="text-danger p-3">${esc(e.message)}</td></tr>`; }
}

function summary(en) {
  const keys = Object.keys(en.changes).filter((k) => !["created_at", "updated_at", "is_archived", "archived_at", "archived_by", "id"].includes(k));
  if (en.operation === "INSERT") {
    const name = en.changes.name || en.changes.full_name || en.changes.form_name || en.changes.meeting_number || en.changes.filename;
    return name ? esc(String(name.to)) : `${keys.length} field(s) set`;
  }
  if (en.changes.is_archived) return en.changes.is_archived.to ? "archived" : "restored";
  return keys.slice(0, 4).map((k) => `<code>${esc(k)}</code>: ${esc(show(en.changes[k].from))} &rarr; <b>${esc(show(en.changes[k].to))}</b>`).join("<br>")
    + (keys.length > 4 ? `<br><span class="text-muted">+${keys.length - 4} more</span>` : "");
}

const show = (v) => (v == null ? "—" : typeof v === "object" ? JSON.stringify(v) : String(v));

function draw() {
  $("#logBody").innerHTML = entries.length ? entries.map((en) => `<tr>
      <td class="text-muted" style="white-space:nowrap">${esc(fmtDateTime(en.at))}</td><td>${esc(en.actor)}</td>
      <td>${esc(en.operation === "INSERT" ? "Created" : "Changed")} ${esc(en.table_label.toLowerCase())} <span class="text-muted">#${esc(en.record_id)}</span></td>
      <td style="font-size:.78rem">${summary(en)}</td></tr>`).join("")
    : `<tr><td colspan="4" class="text-center text-muted py-4">No activity recorded yet.</td></tr>`;
  $("#logCount").textContent = `(${entries.length}${more ? "+" : ""} entries)`;
  $("#logInfo").textContent = more ? "Showing the most recent entries" : "";
  $("#logMore").style.display = more ? "" : "none";
  filter();
}

function filter() {
  const q = ($("#logSearch").value || "").toLowerCase();
  $$("#logBody tr").forEach((tr) => { tr.style.display = tr.textContent.toLowerCase().indexOf(q) >= 0 ? "" : "none"; });
}

function exportCsv() {
  const rows = [["Timestamp", "User", "Action", "Record type", "Record", "Changes"]];
  entries.forEach((en) => rows.push([fmtDateTime(en.at), en.actor, en.operation === "INSERT" ? "Created" : "Changed", en.table_label, en.record_id,
    Object.entries(en.changes).filter(([k]) => !["created_at", "updated_at"].includes(k)).map(([k, v]) => `${k}: ${show(v.from)} -> ${show(v.to)}`).join("; ")]));
  downloadFile(`${slug(company().name)}_activity_log.csv`, toCSV(rows), "text/csv;charset=utf-8;");
  toast("Activity log exported");
}
