/* Notifications - what needs a person's attention, company by company (read only; no e-mail is sent).

   The bell in the top bar carries the total. The numbers come from the server and agree with the Overview page. */

import * as api from "./api.js";
import { $, esc } from "./util.js";

const LABELS = [["overdue_filings", "overdue filing", "overdue filings"], ["overdue_tasks", "overdue task", "overdue tasks"],
  ["due_soon_tasks", "task due within 7 days", "tasks due within 7 days"], ["pending_confirmations", "confirmation waiting", "confirmations waiting"],
  ["rules_action_required", "rule needing action", "rules needing action"]];

export function setBadge(n) {
  const el = $("#notifCount");
  el.textContent = n > 99 ? "99+" : String(n);
  el.classList.toggle("d-none", !n);
}

export async function refreshBadge() {
  try { setBadge((await api.get("/notifications")).total); } catch (e) { setBadge(0); }
}

function summary(counts) {
  const parts = LABELS.filter(([k]) => counts[k]).map(([k, one, many]) => `${counts[k]} ${counts[k] === 1 ? one : many}`);
  return parts.join(" · ") || "nothing needs attention";
}

export async function render() {
  $("#crumb").textContent = "";
  $("#pageTitle").textContent = "Notifications";
  $("#pageSub").textContent = "What needs attention in the companies you can open - click an item to go there";
  $("#view").innerHTML = `<div class="tbl-card p-4 text-muted">Loading…</div>`;
  let data;
  try { data = await api.get("/notifications"); }
  catch (e) { $("#view").innerHTML = `<div class="tbl-card p-4 text-danger">${esc(e.message)}</div>`; return; }
  setBadge(data.total);
  $("#view").innerHTML = data.companies.length
    ? data.companies.map((c) => `<div class="tbl-card notif-card">
        <div class="notif-head"><span class="co">${esc(c.company_name)}</span><span class="sum">${esc(summary(c.counts))}</span></div>
        ${c.items.length ? c.items.map((i) => `<div class="att-item" role="button" data-company="${esc(c.company_id)}" data-go="${esc(i.view)}">
            <span class="att-dot att-${esc(i.level)}"></span><div><div class="fw-semibold">${esc(i.title)}</div>
            <div class="text-muted small">${esc(i.detail)}</div></div></div>`).join("")
          : `<div class="p-3 text-muted small">Nothing needs attention.</div>`}</div>`).join("")
    : `<div class="tbl-card p-5 text-center text-muted">You do not have access to any company yet.</div>`;
  $("#view").onclick = (e) => {
    const item = e.target.closest("[data-go]");
    if (item) location.hash = `#/company/${item.dataset.company}/${item.dataset.go}`;
  };
}
