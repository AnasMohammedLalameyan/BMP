/* Dashboard Overview: the same stat tiles / progress bar / segment cards as the approved dashboard,
   fed by the live database instead of the old checklist. */

import { $, esc } from "./util.js";
import { company, state } from "./state.js";
import { GROUP_ICONS } from "./sidebar.js";

function tile(cls, label, value, sub, color) {
  return `<div class="col-6 col-lg-3"><div class="stat ${cls}"><div class="k">${esc(label)}</div>
    <div class="v" ${color ? `style="color:var(${color})"` : ""}>${value}</div>
    ${sub ? `<div class="text-muted" style="font-size:.72rem">${sub}</div>` : ""}</div></div>`;
}

export function renderOverview() {
  const co = company();
  const o = state.overview;
  $("#crumb").textContent = "Working Papers — Overview";
  $("#pageTitle").textContent = co ? co.name : "Compliance Dashboard";
  $("#pageSub").innerHTML = co
    ? `${esc(co.cin)} &middot; ${esc(co.category || "")}${co.is_listed ? " &middot; Listed" : ""} &middot; ${state.fy ? "FY " + esc(state.fy) : "All years"}`
    : "Select a company to begin.";
  if (!o) { $("#view").innerHTML = `<div class="tbl-card p-4 text-muted">Loading…</div>`; return; }
  const t = o.tiles, r = o.rules;

  const tiles = `<div class="row g-3 mb-4">
    ${tile("b-all", "Directors on the board", t.directors, `${t.independent} independent &middot; ${t.women} woman director${t.women === 1 ? "" : "s"}`)}
    ${tile("b-all", "Shareholders", t.shareholders, "current holders on record")}
    ${tile("b-ok", "Meetings held", t.meetings_held, `FY ${esc(o.fy)} &middot; ${t.meetings_planned} planned`, "--ok")}
    ${tile("b-prog", "Filings recorded", `${t.filed}<small> / ${t.filings} filed</small>`, "government forms tracked")}
    ${tile(t.overdue_filings ? "b-no" : "b-ok", "Overdue filings", t.overdue_filings, t.overdue_filings ? "past due and not filed" : "nothing overdue", t.overdue_filings ? "--no" : "--ok")}
    ${tile(t.overdue_tasks ? "b-part" : "b-prog", "Open tasks", t.open_tasks, t.overdue_tasks ? `${t.overdue_tasks} past due date` : "across all activities", t.overdue_tasks ? "--part" : "")}
    ${tile(r.action_required ? "b-no" : "b-ok", "Rules needing action", r.action_required, `of ${r.total} applicability rules`, r.action_required ? "--no" : "--ok")}
    ${tile("b-all", "Rules evaluated", `${r.total - r.unevaluated}<small> / ${r.total}</small>`, `for FY ${esc(o.fy)}`)}
  </div>`;

  const seg = (n, color) => (r.total ? Math.round((n / r.total) * 100) : 0);
  const rulesBar = `<div class="tbl-card p-3 p-md-4 mb-4">
    <div class="d-flex justify-content-between align-items-center mb-2">
      <strong class="text-brand">Applicability rules &middot; FY ${esc(o.fy)}</strong>
      <span class="text-muted small"><a role="button" data-view="rules">open the rules table</a></span>
    </div>
    <div class="progress" style="height:.8rem">
      <div class="progress-bar" style="width:${seg(r.met)}%;background:var(--ok)"></div>
      <div class="progress-bar" style="width:${seg(r.pending)}%;background:var(--prog)"></div>
      <div class="progress-bar" style="width:${seg(r.action_required)}%;background:var(--no)"></div>
      <div class="progress-bar" style="width:${seg(r.not_applicable)}%;background:#cbd5e1"></div>
    </div>
    <div class="legend mt-3">
      <span><i class="dot" style="background:var(--ok)"></i>Met (${r.met})</span>
      <span><i class="dot" style="background:var(--prog)"></i>Pending (${r.pending})</span>
      <span><i class="dot" style="background:var(--no)"></i>Action required (${r.action_required})</span>
      <span><i class="dot" style="background:#cbd5e1"></i>Not applicable (${r.not_applicable})</span>
      <span><i class="dot" style="background:#eef2f7;border:1px solid #cbd5e1"></i>Not yet evaluated (${r.unevaluated})</span>
    </div></div>`;

  const attention = `<div class="tbl-card mb-4"><div class="p-3 pb-2 fw-bold text-brand">Needs attention
      <span class="text-muted fw-normal">(${o.attention.length})</span></div>
    ${o.attention.length ? o.attention.map((a) => `<div class="att-item" data-view="${esc(a.view)}" role="button">
        <span class="att-dot att-${esc(a.level)}"></span>
        <div><div class="fw-semibold">${esc(a.title)}</div><div class="text-muted" style="font-size:.76rem">${esc(a.detail)}</div></div></div>`).join("")
      : `<div class="px-3 pb-3 text-muted">Nothing needs attention right now.</div>`}</div>`;

  const cards = `<h2 class="h6 fw-bold text-brand mb-2">Compliance segments</h2><div class="row g-3">${o.segments.map((g) => {
    const total = g.entities.reduce((s, e) => s + e.count, 0);
    const chips = g.entities.map((e) => `<span class="sec-chip" data-view="entity:${esc(e.key)}">${esc(e.label)} <b>${e.count}</b></span>`).join(" ");
    return `<div class="col-12 col-xl-4"><div class="tbl-card grp-card p-3 h-100" data-view="entity:${esc(g.entities[0].key)}">
      <div class="d-flex align-items-center gap-2 mb-2"><span class="grp-ic">${GROUP_ICONS[g.icon] || GROUP_ICONS.fin}</span>
        <div><div class="fw-bold text-brand">${esc(g.title)}</div>
          <div class="text-muted" style="font-size:.78rem">${g.entities.length} record types &middot; ${total} records</div></div></div>
      <div class="d-flex flex-wrap gap-1 mt-2">${chips}</div></div></div>`;
  }).join("")}</div>`;

  $("#view").innerHTML = tiles + attention + rulesBar + cards;
}

export function updateOverallBadge() {
  const badge = $("#overallBadge");
  const o = state.overview;
  if (!o) { badge.textContent = "—"; badge.className = "badge-soft bs-na d-none d-sm-inline"; return; }
  const n = o.attention.length;
  badge.textContent = n ? `${n} need${n === 1 ? "s" : ""} attention` : "All clear";
  badge.className = `badge-soft ${n ? "bs-no" : "bs-ok"} d-none d-sm-inline`;
}
