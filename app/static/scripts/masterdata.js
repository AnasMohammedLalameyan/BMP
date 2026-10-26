/* Master Data - the company's standing record, in the approved dashboard's card layout, grouped into four tabs.

   General Info & Registration: the company profile (every field, saved as each one is changed - same behaviour as the approved Master Data
   screen), the board, business activities, group companies, auditors and the registrar.
   Capital Structure & Financials: share classes, the capital summary, capital events, financials by year and the holders summary.
   Charges & Borrowings: loans and deposits, an ECB summary and the (not yet modelled) charge register.
   Statutory Registers: read-only registers composed from records that already exist, each with a CSV export.

   Each tab loads its data the first time it is opened. Every card sits in exactly one tab. */

import * as api from "./api.js";
import { canWriteCompany, company, entityMeta, state } from "./state.js";
import { $, ceasedInFy, directorShown, downloadFile, esc, fmtDate, fmtDateDMY, fmtNumber, showHistorical, slug, toast, toCSV } from "./util.js";
import { clearErrors, collect, displayValue, fieldHTML, hydrateFk, sectionsFor, showErrors } from "./form.js";
import { mountList } from "./entity.js";
import { mountTabs } from "./tabs.js";

let row = null;

function card(title, note, hostId, wide = true) {
  return `<section class="md-card ${wide ? "md-wide" : ""}">
    <div class="md-h-row"><h3 class="md-h">${esc(title)}</h3></div>
    ${note ? `<div class="md-note text-muted">${note}</div>` : ""}
    <div id="${hostId}"></div></section>`;
}

export async function render(onChange) {
  const co = company();
  $("#crumb").textContent = "";
  $("#pageTitle").textContent = "Master Data";
  $("#pageSub").textContent = "Company profile, board, share capital and standing records — every field of the system of record, kept once and used everywhere";
  if (!co) { $("#view").innerHTML = `<div class="tbl-card p-5 text-center text-muted">Select a company to see its master data.</div>`; return; }
  mountTabs($("#view"), [
    { id: "general", label: "General Info & Registration", render: (el) => drawGeneral(el, onChange) },
    { id: "capital", label: "Capital Structure & Financials", render: drawCapital },
    { id: "charges", label: "Charges & Borrowings", render: drawCharges },
    { id: "registers", label: "Statutory Registers", render: drawRegisters },
  ], { active: state.tab });
}

/* ---------- tab 1: General Info & Registration ---------- */

async function drawGeneral(el, onChange) {
  el.innerHTML = `<div class="tbl-card p-4 text-muted">Loading…</div>`;
  try { row = (await api.getRecord("company", state.companyId)).row; }
  catch (e) { el.innerHTML = `<div class="tbl-card p-4 text-danger">${esc(e.message)}</div>`; return; }

  const meta = entityMeta("company");
  const editable = canWriteCompany() && meta.can_write;
  const secs = sectionsFor(meta);
  el.innerHTML = `<div class="md-layout">
    <section class="md-card md-wide">
      <div class="md-h-row"><h3 class="md-h">Company profile <span class="md-saved" id="mdSaved"></span></h3>
        <span class="small text-muted">${editable ? "Changes save as you leave each field." : "You have read-only access to this company."}</span></div>
      <div id="mdProfile">${secs.map((s) => `<div class="rec-section"><h4>${esc(s.title)}</h4><div class="rec-grid">${
        s.cols.map((c) => fieldHTML("company", c, row, { readonly: !editable || !c.writable, fixed: !c.writable })).join("")}</div></div>`).join("")}</div>
    </section>
    ${card("Directors & KMP", `Everyone who has served on the board. <a role="button" data-view="directors">Open the Directors panel</a>`, "mdDirectors")}
    ${card("Business activities", "", "mdAct")}
    ${card("Holding / subsidiary / associate companies", "", "mdRel")}
    ${card("Statutory auditors", "", "mdAud")}
    ${card("Registrar & Transfer Agent", "", "mdRta")}
  </div>`;

  const root = $("#mdProfile");
  hydrateFk(root, null);
  if (editable) {
    root.addEventListener("change", async (e) => {
      const input = e.target.closest("[data-f]");
      if (!input) return;
      clearErrors(root);
      const payload = collect(root, row);
      if (!Object.keys(payload).length) return;
      payload.updated_at = row.updated_at;
      try {
        row = (await api.updateRecord("company", state.companyId, payload)).row;
        const found = state.companies.find((c) => c.id === state.companyId);
        if (found) { found.name = row.name; found.cin = row.cin; found.is_listed = row.is_listed; }
        $("#mdSaved").textContent = "✓ saved";
        setTimeout(() => { const s = $("#mdSaved"); if (s) s.textContent = ""; }, 2000);
        if (onChange) onChange();
      } catch (err) {
        toast(`Could not save: ${err.message}`);
        showErrors(root, err.fields);
      }
    });
  }

  // standing records: live lists that open the full record on click
  const reg = async () => {
    const { rows } = await api.get(`/companies/${state.companyId}/directors-register`, { include_ceased: "true", fy: state.fy || undefined });
    let historical = showHistorical();
    const drawDirectors = () => {
      const list = historical ? rows : rows.filter((r) => directorShown(r, state.fy));
      const empty = !rows.length ? "No directors recorded." : state.fy ? `No directors were active in ${state.fy}` : "No current directors.";
      $("#mdDirectors").innerHTML = rows.length
        ? `<div class="form-check mb-2 no-print"><input class="form-check-input" type="checkbox" id="mdHistorical" ${historical ? "checked" : ""}>
          <label class="form-check-label small" for="mdHistorical">Show Historical/Ceased Directors</label></div>
          <div class="tbl-card"><div class="table-responsive"><table class="table chk-table md-dir-table align-middle mb-0"><thead><tr>
          <th>Name</th><th>DIN</th><th>Designation</th><th>Appointed</th><th>Ceased</th><th>Address</th><th>Phone Number</th></tr></thead><tbody>${list.length ? list.map((r) => `
          <tr class="${r.is_current ? "" : "md-ceased"}" data-view="directors" role="button"><td>${esc(r.full_name)}</td><td>${esc(r.din || "—")}</td>
            <td>${esc(r.designation || r.category || "—")}</td><td>${esc(r.start_date)}</td><td>${esc(r.end_date || "—")}${ceasedInFy(r.end_date, state.fy) ? ` <span class="pill pill-no">Ceased on ${esc(fmtDateDMY(r.end_date))}</span>` : ""}</td>
            <td class="cell-wrap">${esc(r.address || "—")}</td><td class="text-nowrap">${esc(r.phone || "—")}</td></tr>`).join("")
            : `<tr><td colspan="7" class="text-center text-muted py-3">${esc(empty)}</td></tr>`}
          </tbody></table></div></div>`
        : `<div class="text-muted small">${esc(empty)}</div>`;
      const box = $("#mdHistorical");
      if (box) box.addEventListener("change", () => { historical = box.checked; showHistorical(historical); drawDirectors(); });
    };
    drawDirectors();
  };
  reg();
  mountList($("#mdAct"), "company_business_activity", { size: 8 });
  mountList($("#mdRel"), "company_relationship", { size: 8 });
  mountList($("#mdAud"), "auditor", { size: 8 });
  mountList($("#mdRta"), "company_rta", { size: 8 });
}

/* ---------- tab 2: Capital Structure & Financials ---------- */

function drawCapital(el) {
  el.innerHTML = `<div class="md-layout">
    ${card("Share classes", "", "mdClasses")}
    ${card("Share capital", "Authorised, issued, subscribed and paid-up capital by year and class of share.", "mdCapital")}
    ${card("Capital events", "", "mdEvents")}
    ${card("Financials by year", "Turnover, net worth, profit, reserves, borrowings, CSR spend and the Sec 185 / 186 limits.", "mdFin")}
    ${card("Shareholders and their holdings", `A change in holding closes the old row and opens a new one, so the dates keep the history.
      <a role="button" data-view="shareholders">Open the Shareholders view</a> for the cap table, allotments and transfers.`, "mdHold")}
  </div>`;
  mountList($("#mdClasses"), "share_class", { size: 8 });
  mountList($("#mdCapital"), "capital_snapshot", { size: 8 });
  mountList($("#mdEvents"), "capital_event", { size: 8 });
  mountList($("#mdFin"), "company_financials", { size: 8, useFy: false });
  mountList($("#mdHold"), "shareholding", { size: 10, useFy: false });
}

/* ---------- tab 3: Charges & Borrowings ---------- */

async function drawCharges(el) {
  el.innerHTML = `<div class="md-layout">
    ${card("Loans and deposits", "", "mdLoans")}
    ${card("External commercial borrowings (ECB)", "", "mdEcb")}
    <section class="md-card md-wide"><div class="md-h-row"><h3 class="md-h">Charge register</h3></div>
      <div class="p-3 text-center text-muted border rounded" id="mdCharges"><div class="fw-semibold">No charge register in the approved data model</div>
        <div class="small">Charges created on the company's assets are not recorded anywhere in the database today. If BMP needs this register, it has to be added to the data model first.</div></div></section>
  </div>`;
  mountList($("#mdLoans"), "loan_deposit", { size: 8 });
  const host = $("#mdEcb");
  try {
    const { total } = await api.listEntity("ecb", { company_id: state.companyId, size: 1 });
    host.innerHTML = `<div class="text-muted">${total ? `${total} ECB record${total === 1 ? "" : "s"} on file.` : "No ECB records on file."}
      <a role="button" data-view="foreign">Open ODI / ECB / DI / Foreign Investments</a></div>`;
  } catch (e) { host.innerHTML = `<div class="text-danger small">${esc(e.message)}</div>`; }
}

/* ---------- tab 4: Statutory Registers (read only, composed from existing records) ---------- */

const exports = new Map();      // register id -> CSV rows, for the export buttons

function registerCard(id, title, note, header, csvRows, bodyHTML) {
  exports.set(id, { name: `${slug(title)}.csv`, rows: [header, ...csvRows] });
  return `<section class="md-card md-wide"><div class="md-h-row"><h3 class="md-h">${esc(title)}</h3>
      <button class="btn btn-sm btn-outline-brand no-print" type="button" data-export="${esc(id)}">Export CSV</button></div>
    ${note ? `<div class="md-note text-muted">${esc(note)}</div>` : ""}
    <div class="tbl-card"><div class="table-responsive"><table class="table chk-table align-middle mb-0"><thead><tr>${header.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead>
      <tbody>${bodyHTML || `<tr><td colspan="${header.length}" class="text-center text-muted py-3">Nothing recorded.</td></tr>`}</tbody></table></div></div></section>`;
}

/** A register drawn from a record type: its list columns, read only. */
async function fromEntity(id, title, key, note) {
  const meta = entityMeta(key);
  if (!meta) return "";
  const { rows } = await api.listEntity(key, { company_id: state.companyId, size: 500 });
  const cols = meta.list.map((n) => meta.columns.find((c) => c.name === n)).filter(Boolean);
  const text = (c, r) => (r._labels && r._labels[c.name]) || (r[c.name] == null ? "" : String(r[c.name]));
  return registerCard(id, title, note, cols.map((c) => c.label), rows.map((r) => cols.map((c) => text(c, r))),
    rows.map((r) => `<tr>${cols.map((c) => `<td>${displayValue(c, r)}</td>`).join("")}</tr>`).join(""));
}

const NO_SOURCE = [["Register of charges", "Charges are not part of the approved data model."],
  ["Register of debenture holders", "Debentures are not part of the approved data model."],
  ["Register of sweat equity shares", "Sweat equity issues are not part of the approved data model."]];

async function drawRegisters(el) {
  el.innerHTML = `<div class="tbl-card p-4 text-muted">Loading the registers…</div>`;
  try {
    const [people, cap, classes] = await Promise.all([
      api.get(`/companies/${state.companyId}/directors-register`, { include_ceased: "true" }),
      api.get("/calc/v_shareholding_percent", { company_id: state.companyId }),
      api.getOptions("share_class", { company_id: state.companyId })]);
    const label = Object.fromEntries(classes.options.map((o) => [o.id, o.label]));
    const directors = registerCard("directors", "Register of directors and key managerial personnel",
      "Every board stint with its dates. Composed from the Directors records; change them in the Directors panel.",
      ["Name", "DIN", "Designation", "Appointed", "Ceased", "Reason"],
      people.rows.map((r) => [r.full_name, r.din, r.designation, r.start_date, r.end_date, r.cessation_reason]),
      people.rows.map((r) => `<tr><td>${esc(r.full_name)}</td><td>${esc(r.din || "—")}</td><td>${esc(r.designation || "—")}</td><td>${esc(fmtDate(r.start_date))}</td>
        <td>${r.end_date ? esc(fmtDate(r.end_date)) : '<span class="pill pill-ok">Serving</span>'}</td><td class="cell-wrap">${esc(r.cessation_reason || "—")}</td></tr>`).join(""));
    const members = registerCard("members", "Register of members",
      "Current holders and the percentage of their class, as calculated by the database. Change holdings in the Shareholders view.",
      ["Shareholder", "Category", "Class", "Shares", "Holding %"],
      cap.rows.map((r) => [r.shareholder_name, r.shareholder_category, label[r.share_class_id] || "", r.number_of_shares, r.holding_percent]),
      cap.rows.map((r) => `<tr><td>${esc(r.shareholder_name)}</td><td>${esc(r.shareholder_category || "—")}</td><td>${esc(label[r.share_class_id] || "—")}</td>
        <td class="num text-end">${esc(fmtNumber(r.number_of_shares))}</td><td class="num text-end">${esc(fmtNumber(r.holding_percent, 4))}%</td></tr>`).join(""));
    const parts = await Promise.all([
      fromEntity("loans185", "Register of loans to directors (Sec 185)", "s185_loan", "Read only; edit these records under Financial & Legal."),
      fromEntity("loans186", "Register of loans and investments (Sec 186)", "s186_transaction", "Read only; edit these records under Financial & Legal."),
      fromEntity("rpt", "Register of contracts with related parties (Sec 188)", "s188_related_party_txn", "Read only; edit these records under Financial & Legal.")]);
    el.innerHTML = `<div class="md-layout">${directors}${members}${parts.join("")}
      ${NO_SOURCE.map(([t, why]) => `<section class="md-card md-wide"><div class="md-h-row"><h3 class="md-h">${esc(t)}</h3></div>
        <div class="p-3 text-center text-muted border rounded"><div class="fw-semibold">No source table</div><div class="small">${esc(why)}</div></div></section>`).join("")}</div>`;
  } catch (e) { el.innerHTML = `<div class="tbl-card p-4 text-danger">${esc(e.message)}</div>`; return; }
  el.onclick = (e) => {
    const b = e.target.closest("[data-export]");
    if (!b) return;
    const file = exports.get(b.dataset.export);
    if (file) downloadFile(file.name, toCSV(file.rows), "text/csv");
  };
}
