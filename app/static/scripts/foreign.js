/* ODI / ECB / DI / Foreign Investments - one tracking view for a company's overseas direct investment, external commercial borrowings and
   foreign investment received (FC-GPR / FC-TRS).

   A tracking view only: it lists the records and adds a summary strip. It has no rules, due-date logic or activity templates of its own;
   the "next due" dates are simply the earliest date already recorded on a record that is still open. */

import * as api from "./api.js";
import { company, state } from "./state.js";
import { $, esc, fmtDate, fmtNumber } from "./util.js";
import { mountList } from "./entity.js";

const today = () => new Date().toISOString().slice(0, 10);

/* what the summary strip reads from each record type: the amount column and the date that says what is next due */
const SECTIONS = [
  { id: "odi", key: "odi", title: "Overseas Direct Investment (ODI)", amount: "total_investment_inr",
    due: (r) => (r.filing_date ? null : r.board_approval_date), dueLabel: "approved, not yet filed" },
  { id: "ecb", key: "ecb", title: "External Commercial Borrowings (ECB)", amount: "amount_inr",
    due: (r) => r.maturity_date, dueLabel: "maturity" },
  { id: "di", key: "foreign_investment", title: "Direct Investment (DI) / Foreign investment received", amount: "amount_inr",
    due: (r) => (r.filing_date ? null : r.filing_due_date), dueLabel: "filing due" },
];

export async function render() {
  const co = company();
  $("#crumb").textContent = "";
  $("#pageTitle").textContent = "ODI / ECB / DI / Foreign Investments";
  $("#pageSub").innerHTML = `${esc(co ? co.name : "")} &middot; <span class="text-muted">overseas investment, external borrowings and foreign investment received — tracking only</span>`;
  $("#view").innerHTML = `<div id="foreign-investments-tab">
    <div class="row g-3 mb-3" id="fiSummary">${SECTIONS.map((s) => `<div class="col-md-4"><div class="tbl-card p-3" data-sum="${s.id}">
        <div class="small text-muted">${esc(s.title)}</div><div class="text-muted">Loading…</div></div></div>`).join("")}</div>
    <div class="md-layout">
      <section class="md-card md-wide"><div class="md-h-row"><h3 class="md-h">Overseas Direct Investment (ODI)</h3></div><div id="fiOdi"></div></section>
      <section class="md-card md-wide"><div class="md-h-row"><h3 class="md-h">ODI step-down subsidiaries</h3></div><div id="fiStep"></div></section>
      <section class="md-card md-wide"><div class="md-h-row"><h3 class="md-h">External Commercial Borrowings (ECB)</h3></div><div id="fiEcb"></div></section>
      <section class="md-card md-wide"><div class="md-h-row"><h3 class="md-h">DI / Foreign investment received (FC-GPR and FC-TRS)</h3></div><div id="fiDi"></div></section>
    </div></div>`;
  mountList($("#fiOdi"), "odi", { size: 8, useFy: false });
  mountList($("#fiStep"), "odi_step_down_subsidiary", { size: 8, useFy: false });
  mountList($("#fiEcb"), "ecb", { size: 8, useFy: false });
  mountList($("#fiDi"), "foreign_investment", { size: 8, useFy: false });
  SECTIONS.forEach(summary);
}

async function summary(s) {
  const host = document.querySelector(`[data-sum="${s.id}"]`);
  try {
    const { rows, total } = await api.listEntity(s.key, { company_id: state.companyId, size: 500 });
    const sum = rows.reduce((t, r) => t + (Number(r[s.amount]) || 0), 0);
    const next = rows.map(s.due).filter((d) => d && d >= today()).sort()[0] || rows.map(s.due).filter(Boolean).sort()[0];
    host.innerHTML = `<div class="small text-muted">${esc(s.title)}</div>
      <div class="fs-4 fw-bold">${esc(total)} <span class="fs-6 fw-normal text-muted">record${total === 1 ? "" : "s"}</span></div>
      <div class="small">Total ${total ? "&#8377; " + esc(fmtNumber(sum, 2)) : "—"}</div>
      <div class="small text-muted">Next ${esc(s.dueLabel)}: ${next ? esc(fmtDate(next)) : "—"}</div>`;
  } catch (e) { host.innerHTML = `<div class="small text-danger">${esc(e.message)}</div>`; }
}
