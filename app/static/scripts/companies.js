/* The Companies landing page (same table style as the approved dashboard's company list) and the
   "Add company" dialog for administrators. */

import * as api from "./api.js";
import { entityMeta, state } from "./state.js";
import { $, esc, fmtDate, toast } from "./util.js";
import { clearErrors, collect, fieldHTML, hydrateFk, sectionsFor, showErrors } from "./form.js";
import { closeModal, openModal } from "./entity.js";

export function renderCompanies(onOpen, onAdded) {
  const list = state.companies;
  $("#crumb").textContent = "";
  $("#pageTitle").textContent = "Companies";
  $("#pageSub").textContent = `${list.length} ${list.length === 1 ? "company" : "companies"} you can access — click one to open it`;

  const rows = list.map((c) => `<tr class="co-row" data-open-company="${c.id}" role="button" tabindex="0">
      <td><div class="co-name">${esc(c.name)}</div><div class="co-sub">${esc(c.cin)}${c.pan ? " · " + esc(c.pan) : ""}</div></td>
      <td>${esc(c.category || "—")}${c.subcategory ? `<div class="co-sub">${esc(c.subcategory)}</div>` : ""}</td>
      <td>${c.is_listed ? '<span class="pill pill-prog">Listed</span>' : '<span class="pill pill-na">Unlisted</span>'}</td>
      <td class="text-end">${c.directors}</td>
      <td>${esc(fmtDate(c.date_of_incorporation))}</td>
      <td><span class="pill pill-na">${esc(c.access_level)}</span></td>
      <td class="text-end no-print"><span class="co-open">Open &rarr;</span></td>
    </tr>`).join("");

  const body = list.length
    ? `<div class="tbl-card"><div class="table-responsive"><table class="table chk-table co-table all-companies-table align-middle mb-0">
        <thead><tr><th>Company</th><th>Category</th><th>Listing</th><th class="text-end">Directors</th><th>Incorporated</th><th>Your access</th><th></th></tr></thead>
        <tbody>${rows}</tbody></table></div></div>`
    : `<div class="tbl-card p-5 text-center text-muted"><div class="mb-3">You do not have access to any company yet.</div>
        ${state.user.is_admin ? '<button class="btn btn-brand btn-sm" data-add-company type="button">+ Add the first company</button>' : "Ask an administrator to grant you access."}</div>`;

  $("#view").innerHTML = `${state.user.is_admin ? `<div class="d-flex justify-content-end mb-3 no-print">
      <button class="btn btn-brand" data-add-company type="button">+ Add Company</button></div>` : ""}${body}`;

  $("#view").onclick = (e) => {
    if (e.target.closest("[data-add-company]")) { openAddCompany(onAdded); return; }
    const row = e.target.closest("[data-open-company]");
    if (row) onOpen(Number(row.dataset.openCompany));
  };
}

export function openAddCompany(onAdded) {
  const meta = entityMeta("company");
  const secs = sectionsFor(meta, { includeReadonly: false });
  const entry = openModal(`
    <div class="modal-header"><div><div class="rec-title">Add a company</div>
      <div class="small text-muted">You will be given administrator access to it.</div></div>
      <button type="button" class="btn-close" data-close></button></div>
    <div class="modal-body"><div id="coErr"></div><div id="coFields">${secs.map((s) =>
      `<div class="rec-section"><h4>${esc(s.title)}</h4><div class="rec-grid">${
        s.cols.map((c) => fieldHTML("company", c, c.name === "status" ? { status: "active" } : {}, {})).join("")}</div></div>`).join("")}</div></div>
    <div class="modal-footer"><button class="btn btn-outline-secondary" data-close>Cancel</button>
      <button class="btn btn-brand" id="coSave">Add company</button></div>`);
  const root = entry.el.querySelector("#coFields");
  hydrateFk(root, null);
  entry.el.addEventListener("click", async (e) => {
    if (e.target.closest("[data-close]")) { closeModal(entry); return; }
    if (!e.target.closest("#coSave")) return;
    clearErrors(root);
    entry.el.querySelector("#coErr").innerHTML = "";
    const payload = Object.fromEntries(Object.entries(collect(root, null)).filter(([, v]) => v !== null && v !== ""));
    try {
      const { row } = await api.post("/companies", payload);
      toast(`${row.name} added`);
      closeModal(entry);
      if (onAdded) onAdded(row.id);
    } catch (err) {
      entry.el.querySelector("#coErr").innerHTML = `<div class="rec-error">${esc(err.message)}</div>`;
      showErrors(root, err.fields);
    }
  });
}
