/* Shareholders - who holds what, in one panel: the cap table, the allotment log, the transfer register and the shareholders themselves.

   The cap table's percentages are the database's own calculated values (core.v_shareholding_percent, served by /api/calc/...);
   nothing is computed in the browser. Share classes, the share capital summary and capital events describe the company's capital
   rather than its holders, so they live in Master Data (a link at the top jumps there). */

import * as api from "./api.js";
import { company, state } from "./state.js";
import { $, esc, fmtNumber } from "./util.js";
import { mountList } from "./entity.js";
import { mountTabs } from "./tabs.js";

export async function render() {
  const co = company();
  $("#crumb").textContent = "";
  $("#pageTitle").textContent = "Shareholders";
  $("#pageSub").innerHTML = `${esc(co ? co.name : "")} &middot; <span class="text-muted">current holdings, allotments, transfers and the people and entities behind them</span>`;
  $("#view").innerHTML = `<div class="d-flex justify-content-end mb-2 no-print">
      <a role="button" class="small" id="capStructure">Capital structure &rarr; share classes, capital summary and events (Master Data)</a></div><div id="shTabs"></div>`;
  $("#capStructure").addEventListener("click", () => { location.hash = `#/company/${state.companyId}/masterdata/capital`; });
  mountTabs($("#shTabs"), [
    { id: "captable", label: "Cap table", render: drawCapTable },
    { id: "allotments", label: "Allotments", render: (el) => list(el, "Share allotments", "allotment") },
    { id: "transfers", label: "Transfers", render: (el) => list(el, "Share transfers", "share_transfer") },
    { id: "holders", label: "Shareholders", render: (el) => list(el, "Shareholders (people and entities)", "shareholder") },
  ], { active: state.tab });
}

function list(el, title, key) {
  el.innerHTML = `<section class="md-card"><div class="md-h-row"><h3 class="md-h">${esc(title)}</h3></div><div data-l></div></section>`;
  mountList(el.querySelector("[data-l]"), key, { size: 10 });
}

async function drawCapTable(el) {
  el.innerHTML = `<div class="tbl-card p-4 text-muted">Loading…</div>`;
  let calc, classes;
  try {
    [calc, classes] = await Promise.all([api.get("/calc/v_shareholding_percent", { company_id: state.companyId }),
      api.getOptions("share_class", { company_id: state.companyId })]);
  } catch (e) { el.innerHTML = `<div class="tbl-card p-4 text-danger">${esc(e.message)}</div>`; return; }
  const label = Object.fromEntries(classes.options.map((o) => [o.id, o.label]));
  const groups = new Map();
  calc.rows.forEach((r) => {
    if (!groups.has(r.share_class_id)) groups.set(r.share_class_id, []);
    groups.get(r.share_class_id).push(r);
  });
  const body = Array.from(groups.entries()).map(([cls, rows]) => `<tr class="table-light"><td colspan="4" class="fw-semibold">${esc(label[cls] || `Class #${cls}`)}
      <span class="text-muted fw-normal">&middot; ${esc(fmtNumber(rows[0].total_shares))} shares in issue</span></td></tr>
    ${rows.sort((a, b) => b.number_of_shares - a.number_of_shares).map((r) => `<tr><td>${esc(r.shareholder_name)}</td><td>${esc(r.shareholder_category || "—")}</td>
      <td class="num text-end">${esc(fmtNumber(r.number_of_shares))}</td><td class="num text-end" data-percent>${esc(fmtNumber(r.holding_percent, 4))}%</td></tr>`).join("")}`).join("");
  el.innerHTML = `<section class="md-card mb-3"><div class="md-h-row"><h3 class="md-h">Cap table</h3></div>
      <div class="md-note text-muted">Current holdings and each holder's percentage of the shares in their class, as calculated by the database.</div>
      <div class="tbl-card"><div class="table-responsive"><table class="table chk-table cap-table align-middle mb-0">
        <thead><tr><th>Shareholder</th><th>Category</th><th class="text-end">Shares</th><th class="text-end">Holding</th></tr></thead>
        <tbody>${body || `<tr><td colspan="4" class="text-center text-muted py-4">No current holdings recorded.</td></tr>`}</tbody></table></div></div></section>
    <section class="md-card"><div class="md-h-row"><h3 class="md-h">Holding records</h3></div>
      <div class="md-note text-muted">A change in holding closes the old row and opens a new one, so the dates keep the history.</div><div data-l></div></section>`;
  mountList(el.querySelector("[data-l]"), "shareholding", { size: 10, useFy: false });
}
