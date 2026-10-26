/* Applicability Rules - "when does something become required?" for one company and year.

   The rules are rows of data (with their legal reference), not code. Each can carry a recorded evaluation
   (applies / status / the figures used / notes). Two rules are also shown computed straight from the board's
   records, to demonstrate how a rule can be worked out rather than typed. */

import * as api from "./api.js";
import { canWriteCompany, company, state } from "./state.js";
import { $, esc, fmtDateTime, pillClass, words } from "./util.js";
import { openRecord } from "./entity.js";

let data = null;
let filter = "all";
let term = "";

const FILTERS = [["all", "All"], ["action_required", "Action required"], ["pending", "Pending"], ["met", "Met"],
  ["not_applicable", "Not applicable"], ["unevaluated", "Not yet evaluated"]];

function yearInUse() { return state.fy || state.currentFy; }

export async function render(onChange) {
  const co = company();
  $("#crumb").textContent = "";
  $("#pageTitle").textContent = "Applicability Rules";
  $("#pageSub").innerHTML = `${esc(co ? co.name : "")} &middot; FY ${esc(yearInUse())} <span class="text-muted">&middot; ${state.fy ? "" : "All years is selected, so the current year is used &middot; "}
    rules are data with a legal reference; each can carry a recorded evaluation</span>`;
  $("#view").innerHTML = `<div class="tbl-card p-4 text-muted">Loading…</div>`;
  try { data = await api.get(`/companies/${state.companyId}/rules`, { fy: yearInUse() }); }
  catch (e) { $("#view").innerHTML = `<div class="tbl-card p-4 text-danger">${esc(e.message)}</div>`; return; }
  draw(onChange);
}

function statusKey(r) { return r.status || "unevaluated"; }

function computedFor(code) {
  const rows = (data.computed || {})[code] || [];
  if (!rows.length) return "";
  const r = rows.find((x) => !x.financial_year || x.financial_year === data.fy) || rows[0];
  if (code === "RESIDENT_DIRECTOR") return `<span class="pill ${r.has_resident_director ? "pill-ok" : "pill-no"}">${r.has_resident_director ? "Board has a resident director" : "No resident director"}</span>`;
  if (code === "WOMAN_DIRECTOR") return `<span class="pill ${r.has_woman_director ? "pill-ok" : "pill-no"}">${r.has_woman_director ? `${r.woman_director_count} woman director(s)` : "No woman director"}</span>`;
  return "";
}

function draw(onChange) {
  const counts = {};
  data.rules.forEach((r) => { counts[statusKey(r)] = (counts[statusKey(r)] || 0) + 1; });
  const list = data.rules.filter((r) => (filter === "all" || statusKey(r) === filter)
    && (!term || (r.name + r.code + (r.law_reference || "")).toLowerCase().includes(term)));
  const canEdit = canWriteCompany();
  $("#view").innerHTML = `<div class="list-bar no-print"><div class="left">
      ${FILTERS.map(([k, l]) => `<button class="btn btn-sm ${filter === k ? "btn-brand" : "btn-outline-brand"}" data-filter="${k}" type="button">${l}${k !== "all" ? ` (${counts[k] || 0})` : ` (${data.rules.length})`}</button>`).join(" ")}</div>
      <div class="right"><input class="form-control form-control-sm" id="ruleQ" placeholder="Search rules…" value="${esc(term)}"></div></div>
    <div class="tbl-card"><div class="table-responsive"><table class="table chk-table align-middle mb-0">
      <thead><tr><th style="width:44%">Rule</th><th>Applies to</th><th>Status for FY ${esc(data.fy)}</th><th>From the records</th><th class="no-print"></th></tr></thead><tbody>
      ${list.map((r) => `<tr>
        <td><div class="fw-semibold">${esc(r.name)}</div>
          <div class="text-muted" style="font-size:.72rem">${esc(r.law_reference || "")}${r.frequency ? " · " + esc(r.frequency) : ""}${r.responsible_party ? " · " + esc(r.responsible_party) : ""}</div>
          <details class="mt-1"><summary class="text-muted" style="font-size:.72rem;cursor:pointer">How it is decided</summary>
            <div style="font-size:.78rem" class="mt-1"><b>Trigger:</b> ${esc(r.trigger_description || "—")}<br><b>Inputs needed:</b> ${esc(r.inputs_needed || "—")}<br><b>Decides:</b> ${esc(r.decides || "—")}</div></details></td>
        <td style="font-size:.8rem">${esc(r.applies_to_description || "—")}</td>
        <td>${r.status ? `<span class="pill ${pillClass(r.status)}">${esc(words(r.status))}</span>
              <div class="co-sub">${r.applies == null ? "" : r.applies ? "applies" : "does not apply"} · ${esc(fmtDateTime(r.evaluated_on))}</div>${r.notes ? `<div class="co-sub">${esc(r.notes)}</div>` : ""}`
            : '<span class="pill pill-na">Not yet evaluated</span>'}</td>
        <td>${computedFor(r.code) || '<span class="muted-dash">—</span>'}</td>
        <td class="text-end no-print" style="white-space:nowrap">${canEdit ? `<button class="btn btn-sm btn-link p-0" data-eval="${r.rule_id}" data-eid="${r.evaluation_id || ""}" type="button">${r.evaluation_id ? "Update" : "Record evaluation"}</button>` : ""}</td>
      </tr>`).join("") || `<tr><td colspan="5" class="text-center text-muted py-4">No rules match.</td></tr>`}</tbody></table></div></div>
    <div class="text-muted mt-2" style="font-size:.76rem">Each saved evaluation is a new dated record, so the history of a rule's status is kept.
      This is decision support, not legal advice: rules marked for review should be signed off by a BMP professional before use in a filing.</div>`;
  $("#ruleQ").addEventListener("input", (e) => { term = e.target.value.trim().toLowerCase(); draw(onChange); $("#ruleQ").focus(); });
  $("#view").onclick = (e) => {
    const f = e.target.closest("[data-filter]");
    if (f) { filter = f.dataset.filter; draw(onChange); return; }
    const ev = e.target.closest("[data-eval]");
    if (ev) {
      // always a NEW evaluation record: the rule's history is never overwritten
      openRecord("rule_evaluation", null, {
        defaults: { rule_id: Number(ev.dataset.eval), financial_year: data.fy },
        fixed: ["rule_id", "financial_year"], labels: {},
        onSaved: async () => { await render(onChange); if (onChange) onChange(); },
      });
    }
  };
}
