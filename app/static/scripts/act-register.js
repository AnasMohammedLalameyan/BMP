/* The one register view, parameterised by register key: list of meeting cards, compliance strip, and the
   add/edit panel. All eight registers (Board, Audit Committee ... EGM) render through this module. */

import * as minApi from "./act-api.js";
import { canWriteCompany, company, state } from "./state.js";
import { $, esc, fmtDate, toast } from "./util.js";
import { complianceStrip } from "./act-compliance.js";
import { blankAgenda, blankDraft, bodyFrom, captureDraft, draftFrom, panelHTML, presentNames, rosterHTML } from "./act-form.js";
import { openUploadModal } from "./act-upload.js";
import * as ai from "./act-ai.js";

let reg = null;            // the register config {key, name, ref, min, committee, standard}
let data = null;           // last list response
let draft = null;          // the meeting being edited, or null while the list is shown
let roster = [];           // directors on the board on the draft's meeting date
let rosterOk = false;
let onChange = () => {};   // called after a save/archive so the sidebar counts refresh

const chips = (csv) => String(csv || "").split(",").map((s) => s.trim()).filter(Boolean);

/* ---------------------------------------------------------------- list ---- */

function particulars(m) {
  const items = [
    ["Date of notice", m.notice_date ? fmtDate(m.notice_date) : ""], ["Chairman", m.chairman],
    ["Directors present", m.directors_present], ["Invitees", m.invitees_present],
    ["Leave of absence", m.leave_of_absence], ["Signing date", m.signing_date ? fmtDate(m.signing_date) : ""],
    ["Place of signing", m.signing_place], ["Date of entry", m.entry_date ? fmtDate(m.entry_date) : ""],
    ["Attendance sheet", m.attendance_sheet], ["Signed documents", m.signed_documents],
  ].filter(([, v]) => v);
  return items.length ? `<div class="meet-particulars">${items.map(([k, v]) =>
    `<div class="mp-item"><span class="mp-label">${esc(k)}</span><span class="mp-val">${esc(v)}</span></div>`).join("")}</div>` : "";
}

function agendaTable(m) {
  const items = m.agenda || [];
  if (!items.length) return `<div class="text-muted small">No agenda recorded.</div>`;
  const showForms = items.some((a) => chips(a.forms).length);
  const showDocs = items.some((a) => chips(a.docs).length);
  const chipHTML = (csv, cls) => chips(csv).map((c) => `<span class="ag-chip ${cls}">${esc(c)}</span>`).join(" ");
  return `<table class="meet-agenda"><thead><tr><th class="ag-num">#</th><th>Agenda</th>
    ${showForms ? `<th class="ag-forms">Forms filed</th>` : ""}${showDocs ? `<th class="ag-docs">Documents to check</th>` : ""}</tr></thead><tbody>
    ${items.map((a, i) => `<tr><td class="ag-num">${i + 1}</td><td class="ag-item">${esc(a.text)}
      ${a.reg30 === "Yes" ? `<span class="ag-chip ag-reg">Reg 30</span>` : ""}
      ${a.comments ? `<div class="ag-note">${esc(a.comments)}</div>` : ""}</td>
      ${showForms ? `<td>${chipHTML(a.forms, "ag-form")}</td>` : ""}${showDocs ? `<td>${chipHTML(a.docs, "ag-doc")}</td>` : ""}</tr>`).join("")}
    </tbody></table>`;
}

function card(m) {
  const canEdit = canWriteCompany();
  const meta = [m.mode, m.meeting_time, `${m.attendance_present}/${m.attendance_total} present`, m.minutes_status]
    .filter(Boolean).join(" · ");
  return `<div class="tbl-card meet-card mb-3" data-meeting="${m.meeting_id}">
    <div class="meet-head"><div><span class="meet-date">${esc(fmtDate(m.meeting_date))}</span>
      <span class="meet-meta">${esc(meta)}</span></div>
      <div class="meet-actions no-print">${canEdit ? `${ai.noticeButton()}<button class="btn btn-sm btn-link" type="button" data-meet-action="edit">Edit</button>
        <button class="btn btn-sm btn-link text-danger" type="button" data-meet-action="archive">Archive</button>` : ""}</div></div>
    ${particulars(m)}${agendaTable(m)}
    ${m.comments ? `<div class="meet-note">${esc(m.comments)}</div>` : ""}</div>`;
}

function actions() {
  const host = $("#regActions");
  if (draft) { host.innerHTML = ""; return; }
  const canAdd = canWriteCompany();
  const blocked = canAdd && data && !data.committee_available;
  host.innerHTML = `<button class="btn btn-sm btn-outline-brand" type="button" data-meet-action="export">Download Excel</button>
    ${canAdd ? `<button class="btn btn-sm btn-brand" type="button" data-meet-action="add" ${blocked ? "disabled" : ""}
      ${blocked ? `title="This company has no ${esc(reg.name)} constituted. Add it in Master Data first."` : ""}>+ Add meeting</button>` : ""}`;
}

function drawList() {
  actions();
  const ms = data.meetings;
  const note = canWriteCompany() && !data.committee_available
    ? `<div class="alert alert-warning py-2 small">This company has no ${esc(reg.name)} constituted, so meetings cannot be added. Add the committee in Master Data first.</div>` : "";
  $("#view").innerHTML = `<div id="aiAskSlot"></div>${complianceStrip(data.compliance, data.standard)}${note}
    ${ms.length ? ms.map(card).join("") : `<div class="tbl-card p-5 text-center text-muted">No ${esc(reg.name)} recorded for FY ${esc(state.fy)} yet.</div>`}`;
  ai.mountAsk(reg.key);
}

/* ---------------------------------------------------------------- panel ---- */

function cfg() {
  return { modes: data.modes, statuses: data.minutes_statuses };
}

function drawPanel() {
  actions();
  $("#view").innerHTML = panelHTML(draft, roster, cfg());
  ai.mountPanel(host, !draft.meeting_id);
}

async function loadRoster() {
  if (!draft.meeting_date) { roster = []; rosterOk = false; return; }
  try {
    roster = (await minApi.roster(state.companyId, draft.meeting_date)).roster;
    rosterOk = true;
  } catch (e) { roster = []; rosterOk = false; toast(e.message); }
}

function refreshRoster() {
  const box = $("#rosterBox");
  if (!box) return;
  box.innerHTML = rosterHTML(roster, draft.ticked);
  $("#presentText").textContent = presentNames(roster, draft.ticked);
  syncCounts();
}

function syncCounts() {
  const p = $('[data-f="attendance_present"]'), t = $('[data-f="attendance_total"]');
  if (p && !draft._presentTouched) p.value = draft.ticked.size;
  if (t && !draft._totalTouched) t.value = roster.length;
}

async function openPanel(m) {
  draft = m ? draftFrom(m) : blankDraft();
  if (!m) draft.mode = data.modes[0];
  await loadRoster();
  drawPanel();
}

function clearInvalid() {
  document.querySelectorAll(".is-invalid").forEach((el) => el.classList.remove("is-invalid"));
}

async function save() {
  captureDraft($("#meetPanel"), draft);
  clearInvalid();
  const body = bodyFrom(draft, roster);
  if (!rosterOk) delete body.attendance;                // never wipe attendance when the roster could not be loaded
  try {
    if (draft.meeting_id) await minApi.update(reg.key, state.companyId, draft.meeting_id, body);
    else await minApi.create(reg.key, state.companyId, body);
  } catch (e) {
    Object.keys(e.fields || {}).forEach((k) => {
      const el = document.querySelector(`[data-f="${k}"]`);
      if (el) el.classList.add("is-invalid");
    });
    const detail = Object.entries(e.fields || {}).map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`).join("; ");
    toast(e.code === "stale" ? "This meeting was changed by someone else. Cancel, reload, and edit it again."
      : (detail ? `${e.message} ${detail}` : e.message));
    return;
  }
  toast("Meeting saved.");
  draft = null;
  await render();
  onChange();
}

/* ---------------------------------------------------------------- events ---- */

async function onClick(e) {
  const btn = e.target.closest("[data-meet-action]");
  if (!btn) return;
  const act = btn.dataset.meetAction;
  const id = btn.closest("[data-meeting]") ? Number(btn.closest("[data-meeting]").dataset.meeting) : null;
  if (act === "export") {
    try { await minApi.exportXlsx(state.companyId, state.fy, reg.key); } catch (err) { toast(err.message); }
  } else if (act === "add") await openPanel(null);
  else if (act === "edit") await openPanel(data.meetings.find((m) => m.meeting_id === id));
  else if (act === "archive") {
    if (!window.confirm("Archive this meeting? It stays in the audit history.")) return;
    try { await minApi.archive(id); toast("Meeting archived."); await render(); onChange(); } catch (err) { toast(err.message); }
  } else if (act === "cancel") { draft = null; drawList(); }
  else if (act === "save") await save();
  else if (act === "add-agenda") { captureDraft($("#meetPanel"), draft); draft.agenda.push(blankAgenda()); drawPanel(); }
  else if (act === "rm-agenda") {
    captureDraft($("#meetPanel"), draft);
    draft.agenda.splice(Number(btn.dataset.i), 1);
    if (!draft.agenda.length) draft.agenda.push(blankAgenda());
    drawPanel();
  } else if (act === "tick") {
    const did = Number(btn.dataset.did);
    if (draft.ticked.has(did)) draft.ticked.delete(did); else draft.ticked.add(did);
    refreshRoster();
  } else if (act === "tick-all") { roster.forEach((r) => draft.ticked.add(r.directorship_id)); refreshRoster(); }
  else if (act === "upload") openUploadModal(host);
  else if (act.startsWith("ai-")) await ai.handle(act, btn, host);
}

async function onChangeEvent(e) {
  if (!draft) return;
  const el = e.target;
  if (el.dataset && el.dataset.f === "meeting_date") {
    captureDraft($("#meetPanel"), draft);
    await loadRoster();
    draft.ticked = new Set([...draft.ticked].filter((id) => roster.some((r) => r.directorship_id === id)));
    drawPanel();
  }
}

function onInput(e) {
  if (!draft || !e.target.dataset) return;
  if (e.target.dataset.f === "attendance_present") draft._presentTouched = true;
  if (e.target.dataset.f === "attendance_total") draft._totalTouched = true;
}

/* What the upload flow may do to the open draft. */
export const host = {
  draft: () => draft,
  roster: () => roster,
  capture: () => captureDraft($("#meetPanel"), draft),
  redraw: drawPanel,
  reloadRoster: loadRoster,
  companyId: () => state.companyId,
  register: () => reg.key,
};

let wired = false;

/** Show a register. `onSaved` is called after anything that changes the counts. */
export async function show(config, afterChange) {
  reg = config;
  draft = null;
  onChange = afterChange || (() => {});
  if (!wired) {
    wired = true;
    document.addEventListener("click", (e) => { if ($("#view") && ($("#view").contains(e.target) || $("#regActions").contains(e.target))) onClick(e); });
    document.addEventListener("change", onChangeEvent);
    document.addEventListener("input", onInput);
  }
  $("#crumb").textContent = "Activities Dashboard";
  $("#pageTitle").textContent = reg.name;
  const co = company();
  $("#pageSub").textContent = `${co ? co.name : ""} · FY ${state.fy} · ${reg.ref}`;
  await render();
}

export async function render() {
  $("#view").innerHTML = `<div class="tbl-card p-4 text-muted">Loading…</div>`;
  $("#regActions").innerHTML = "";
  try {
    data = await minApi.list(reg.key, state.companyId, state.fy);
  } catch (e) {
    $("#view").innerHTML = `<div class="tbl-card p-4 text-danger">${esc(e.message)}</div>`;
    return;
  }
  drawList();
}

export const isEditing = () => !!draft;
