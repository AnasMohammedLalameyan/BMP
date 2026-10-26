/* All Directors - one row per person, with their roles in every company the signed-in user may open.

   A person is entered once ("Don't Ask Twice"); this page shows where they serve. A client sees only the people
   linked to their own company; the server decides, this page just draws what it is given. */

import * as api from "./api.js";
import { $, debounce, downloadFile, esc, fmtDate, toCSV } from "./util.js";
import { openRecord } from "./entity.js";

let people = [];

export async function render() {
  $("#crumb").textContent = "";
  $("#pageTitle").textContent = "All Directors";
  $("#pageSub").textContent = "Every person once, with their roles in all the companies you can open";
  $("#view").innerHTML = `<div class="list-bar no-print">
      <div class="left"><input class="form-control form-control-sm" id="adSearch" placeholder="Search name, DIN or company…" style="min-width:280px"></div>
      <div class="right"><button class="btn btn-sm btn-outline-brand" id="adExport" type="button">Export CSV</button></div></div>
    <div id="adBody"><div class="tbl-card p-4 text-muted">Loading…</div></div>`;
  $("#adSearch").addEventListener("input", debounce((e) => load(e.target.value.trim()), 300));
  $("#adExport").addEventListener("click", exportCsv);
  $("#view").onclick = (e) => {
    const role = e.target.closest("[data-company]");
    if (role) { location.hash = `#/company/${role.dataset.company}/directors`; return; }
    const tr = e.target.closest("tr[data-person]");
    if (tr) openRecord("director", tr.dataset.person);
  };
  await load("");
}

async function load(q) {
  try { people = (await api.get("/people/directors", q ? { q } : undefined)).people; }
  catch (e) { $("#adBody").innerHTML = `<div class="tbl-card p-4 text-danger">${esc(e.message)}</div>`; return; }
  draw();
}

function roleChip(r) {
  const ended = !r.is_current;
  return `<span class="role-chip ${ended ? "ended" : ""}" role="button" data-company="${esc(r.company_id)}"
      title="Open ${esc(r.company_name)} - Directors">${esc(r.company_name)} &middot; ${esc(r.designation || "Director")}
      <span class="text-muted">${esc(fmtDate(r.start_date))} &ndash; ${r.end_date ? esc(fmtDate(r.end_date)) : "serving"}</span></span>`;
}

function draw() {
  const rows = people.map((p) => `<tr data-person="${esc(p.id)}" role="button">
      <td><div class="co-name">${esc(p.full_name)}</div><div class="co-sub">${p.din ? "DIN " + esc(p.din) : "no DIN"}${p.gender ? ` &middot; ${esc(p.gender)}` : ""}</div></td>
      <td>${p.roles.length ? p.roles.map(roleChip).join("") : '<span class="muted-dash">no role in a company you can open</span>'}</td>
      <td>${esc(p.email || "—")}${p.phone ? `<div class="co-sub">${esc(p.phone)}</div>` : ""}</td></tr>`).join("");
  $("#adBody").innerHTML = `<div class="tbl-card"><div class="table-responsive"><table class="table chk-table align-middle mb-0">
      <thead><tr><th>Person</th><th>Roles across your companies</th><th>Contact</th></tr></thead>
      <tbody>${rows || `<tr><td colspan="3" class="text-center text-muted py-4">No people found.</td></tr>`}</tbody></table></div>
      <div class="pager"><span>${people.length} ${people.length === 1 ? "person" : "people"}</span></div></div>
    <div class="text-muted mt-2" style="font-size:.76rem">Click a person to open their record; click a role to open that company's directors.</div>`;
}

function exportCsv() {
  const head = ["Name", "DIN", "Gender", "Email", "Phone", "Company", "Designation", "Appointed", "Ceased"];
  const lines = [head];
  people.forEach((p) => {
    if (!p.roles.length) lines.push([p.full_name, p.din, p.gender, p.email, p.phone, "", "", "", ""]);
    p.roles.forEach((r) => lines.push([p.full_name, p.din, p.gender, p.email, p.phone, r.company_name, r.designation, r.start_date, r.end_date]));
  });
  downloadFile("all_directors.csv", toCSV(lines), "text/csv");
}
