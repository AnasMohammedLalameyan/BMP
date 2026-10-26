/* The edit panel for one meeting: building it from a draft, reading it back into the draft, the agenda rows and
   the tickable roster of directors. Nothing here talks to the server. */

import { esc } from "./util.js";

export const REG30 = ["NA", "Yes", "No"];

export function blankDraft() {
  return {
    meeting_id: null, meeting_date: "", notice_date: "", meeting_time: "", mode: "", minutes_status: "",
    chairman: "", invitees_present: "", leave_of_absence: "", attendance_sheet: "", attendance_present: "",
    attendance_total: "", entry_date: "", signing_date: "", signing_place: "", signed_documents: "",
    comments: "", updated_at: null, ticked: new Set(), agenda: [blankAgenda()],
    _presentTouched: false, _totalTouched: false,
  };
}

export const blankAgenda = () => ({ id: null, text: "", reg30: "NA", forms: "", docs: "", comments: "" });

/** A draft from a meeting as the server returns it. */
export function draftFrom(m) {
  const d = blankDraft();
  Object.keys(d).forEach((k) => { if (m[k] !== undefined && m[k] !== null && k in m) d[k] = m[k]; });
  d.meeting_id = m.meeting_id;
  d.ticked = new Set((m.attendance || []).filter((a) => a.attended).map((a) => a.directorship_id));
  d.agenda = (m.agenda || []).map((a) => ({ id: a.id, text: a.text, reg30: a.reg30 || "NA", forms: a.forms || "",
    docs: a.docs || "", comments: a.comments || "" }));
  if (!d.agenda.length) d.agenda = [blankAgenda()];
  d._presentTouched = m.attendance_present != null && m.attendance_present !== "";
  d._totalTouched = m.attendance_total != null && m.attendance_total !== "";
  return d;
}

const val = (v) => (v == null ? "" : v);

function field(label, name, v, type = "text", extra = "") {
  return `<div class="rec-field"><label class="form-label small mb-0">${esc(label)}</label>
    <input class="form-control form-control-sm" type="${type}" data-f="${name}" value="${esc(val(v))}" ${extra}></div>`;
}

function select(label, name, options, v) {
  const opts = options.slice();
  if (v && !opts.includes(v)) opts.push(v);
  return `<div class="rec-field"><label class="form-label small mb-0">${esc(label)}</label>
    <select class="form-select form-select-sm" data-f="${name}"><option value="">—</option>
    ${opts.map((o) => `<option ${o === v ? "selected" : ""}>${esc(o)}</option>`).join("")}</select></div>`;
}

export function rosterHTML(roster, ticked) {
  if (!roster.length) return `<div class="text-muted small">No directors were on the board on the date of the meeting.</div>`;
  return `<div class="dir-picker">${roster.map((r) =>
    `<button type="button" class="dir-chip ${ticked.has(r.directorship_id) ? "on" : ""}" data-meet-action="tick"
       data-did="${r.directorship_id}" title="${esc(r.designation || "")}">${esc(r.full_name)}</button>`).join("")}
    <button type="button" class="dir-chip all" data-meet-action="tick-all">+ All present</button></div>`;
}

export function presentNames(roster, ticked) {
  return roster.filter((r) => ticked.has(r.directorship_id)).map((r) => r.full_name).join(", ");
}

function agendaRow(a, i) {
  return `<tr data-ag="${i}" data-id="${a.id == null ? "" : a.id}">
    <td class="ag-num">${i + 1}</td>
    <td><textarea class="form-control form-control-sm" rows="2" data-a="text">${esc(a.text)}</textarea></td>
    <td style="width:84px"><select class="form-select form-select-sm" data-a="reg30">
      ${REG30.map((o) => `<option ${o === a.reg30 ? "selected" : ""}>${o}</option>`).join("")}</select></td>
    <td><input class="form-control form-control-sm" data-a="forms" value="${esc(a.forms)}" placeholder="MGT-14, DIR-12"></td>
    <td><input class="form-control form-control-sm" data-a="docs" value="${esc(a.docs)}"></td>
    <td><input class="form-control form-control-sm" data-a="comments" value="${esc(a.comments)}"></td>
    <td style="width:36px"><button type="button" class="btn btn-sm btn-link text-danger" data-meet-action="rm-agenda"
        data-i="${i}" title="Remove this item" aria-label="Remove this item">×</button></td></tr>`;
}

export function panelHTML(draft, roster, cfg) {
  const d = draft;
  const present = d.attendance_present !== "" && d._presentTouched ? d.attendance_present : d.ticked.size;
  const total = d.attendance_total !== "" && d._totalTouched ? d.attendance_total : roster.length;
  return `<div class="tbl-card p-3 mb-3" id="meetPanel">
    <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
      <strong>${d.meeting_id ? "Edit meeting" : "Add meeting"}</strong>
      <div><span class="small text-muted me-2" id="minutesStatus"></span>
        <button type="button" class="btn btn-sm btn-outline-brand" data-meet-action="upload">↑ Upload minutes to auto-fill</button></div></div>
    <div id="aiSlot"></div>
    <div class="rec-grid mb-2">
      ${field("Date of notice", "notice_date", d.notice_date, "date")}
      ${field("Date of meeting", "meeting_date", d.meeting_date, "date")}
      ${field("Time (start to end)", "meeting_time", d.meeting_time, "text", 'placeholder="e.g. 11:00 AM to 12:00 PM"')}
      ${select("Mode", "mode", cfg.modes, d.mode)}
      ${select("Minutes status", "minutes_status", cfg.statuses, d.minutes_status)}
    </div>
    <div class="rec-grid mb-2">
      <div class="rec-field"><label class="form-label small mb-0">Chairman</label>
        <input class="form-control form-control-sm" data-f="chairman" list="chairList" value="${esc(val(d.chairman))}">
        <datalist id="chairList">${roster.map((r) => `<option value="${esc(r.full_name)}">`).join("")}</datalist></div>
      <div class="rec-field" style="grid-column:span 2"><label class="form-label small mb-0">Directors present</label>
        <div id="rosterBox">${rosterHTML(roster, d.ticked)}</div>
        <div class="small text-muted mt-1" id="presentText">${esc(presentNames(roster, d.ticked))}</div></div>
      ${field("Invitees present", "invitees_present", d.invitees_present)}
    </div>
    <div class="rec-grid mb-2">
      ${field("Leave of absence", "leave_of_absence", d.leave_of_absence)}
      ${field("Present", "attendance_present", present, "number", 'min="0"')}
      ${field("Total (board size)", "attendance_total", total, "number", 'min="0"')}
      ${field("Attendance sheet", "attendance_sheet", d.attendance_sheet)}
    </div>
    <div class="rec-grid mb-3">
      ${field("Date of entry", "entry_date", d.entry_date, "date")}
      ${field("Date of signing", "signing_date", d.signing_date, "date")}
      ${field("Place of signing", "signing_place", d.signing_place)}
      ${field("Signed documents", "signed_documents", d.signed_documents)}
    </div>
    <div class="table-responsive"><table class="meet-agenda" id="agendaTable"><thead><tr>
      <th class="ag-num">#</th><th>Agenda</th><th>Reg 30</th><th>Forms filed</th><th>Documents to be checked</th>
      <th>BMP comments</th><th></th></tr></thead><tbody>${d.agenda.map(agendaRow).join("")}</tbody></table></div>
    <button type="button" class="btn btn-sm btn-outline-brand mt-2" data-meet-action="add-agenda">+ Agenda item</button>
    <div class="rec-field mt-3"><label class="form-label small mb-0">Comments</label>
      <textarea class="form-control form-control-sm" rows="2" data-f="comments">${esc(val(d.comments))}</textarea></div>
    <div class="d-flex gap-2 mt-3">
      <button type="button" class="btn btn-brand" data-meet-action="save">Save</button>
      <button type="button" class="btn btn-outline-secondary" data-meet-action="cancel">Cancel</button></div>
  </div>`;
}

/** Read the form's DOM back into the draft, so a re-render (adding or removing a row) never loses typed text. */
export function captureDraft(root, draft) {
  if (!root) return draft;
  root.querySelectorAll("[data-f]").forEach((el) => { draft[el.dataset.f] = el.value; });
  draft.agenda = Array.from(root.querySelectorAll("tr[data-ag]")).map((tr) => {
    const row = { id: tr.dataset.id ? Number(tr.dataset.id) : null };
    tr.querySelectorAll("[data-a]").forEach((el) => { row[el.dataset.a] = el.value; });
    return row;
  });
  return draft;
}

/* ---- matching names from the minutes to the roster (deliberately conservative) ---- */

const TITLES = /\b(?:mr|mrs|ms|dr|shri|smt|sri|sh|m\/s|ca|cs|justice)\b\.?/gi;

function tokens(name) {
  return String(name || "").toLowerCase().replace(TITLES, " ").split(/[^a-z]+/).filter((t) => t.length > 1);
}

export function namesMatch(a, b) {
  const ta = tokens(a), tb = tokens(b);
  if (!ta.length || !tb.length) return false;
  if (ta.includes(tb[tb.length - 1]) || tb.includes(ta[ta.length - 1])) return true;
  return ta.filter((t) => tb.includes(t)).length >= 2;
}

/** {matched: [directorship_id], unmatched: [name]} for a comma separated list of names. */
export function matchRoster(namesCsv, roster) {
  const matched = [], unmatched = [];
  String(namesCsv || "").split(",").map((s) => s.trim()).filter(Boolean).forEach((n) => {
    const hit = roster.find((r) => namesMatch(n, r.full_name));
    if (hit) { if (!matched.includes(hit.directorship_id)) matched.push(hit.directorship_id); }
    else unmatched.push(n);
  });
  return { matched, unmatched };
}

/** The request body for a save: only what the server stores, agenda rows with no text dropped. */
export function bodyFrom(draft, roster) {
  const num = (v) => (v === "" || v == null ? null : Number(v));
  const body = {};
  ["meeting_date", "notice_date", "meeting_time", "mode", "minutes_status", "chairman", "invitees_present",
    "leave_of_absence", "attendance_sheet", "entry_date", "signing_date", "signing_place", "signed_documents",
    "comments"].forEach((k) => { body[k] = draft[k] === "" ? null : draft[k]; });
  body.attendance_present = draft._presentTouched ? num(draft.attendance_present) : null;
  body.attendance_total = draft._totalTouched ? num(draft.attendance_total) : null;
  body.attendance = roster.map((r) => ({ directorship_id: r.directorship_id, attended: draft.ticked.has(r.directorship_id) }));
  body.agenda = draft.agenda.filter((a) => String(a.text || "").trim()).map((a) => ({
    id: a.id, text: a.text.trim(), reg30: a.reg30 || "NA", forms: a.forms || "", docs: a.docs || "", comments: a.comments || "" }));
  if (draft.updated_at) body.updated_at = draft.updated_at;
  return body;
}
