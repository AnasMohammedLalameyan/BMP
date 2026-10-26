/* Minutes & Meetings - the company's meetings book, laid out as in the approved dashboard: one card per
   meeting with its particulars, agenda and attendance. Board, committee, AGM and EGM meetings all live here. */

import * as api from "./api.js";
import { canWriteCompany, company, state } from "./state.js";
import { $, esc, fmtDate, fmtTime, toast } from "./util.js";
import { closeModal, openModal, openRecord } from "./entity.js";
import { openUploadModal } from "./documents.js";

let meetings = [];

const STATUS = { held: "pill-ok", planned: "pill-prog", cancelled: "pill-no" };

export async function render() {
  const co = company();
  $("#crumb").textContent = "";
  $("#pageTitle").textContent = "Minutes & Meetings";
  $("#pageSub").innerHTML = `${esc(co ? co.name : "")} &middot; ${state.fy ? "FY " + esc(state.fy) : "all years"} `
    + `<span class="text-muted">&middot; board, committee, AGM and EGM meetings with agenda and attendance</span>`;
  $("#view").innerHTML = `<div class="tbl-card p-4 text-muted">Loading…</div>`;
  try { meetings = (await api.get(`/companies/${state.companyId}/meetings-book`, { fy: state.fy || undefined })).meetings; }
  catch (e) { $("#view").innerHTML = `<div class="tbl-card p-4 text-danger">${esc(e.message)}</div>`; return; }
  draw();
}

function particulars(m) {
  const items = [
    ["Type", m.meeting_type], ["Number", m.meeting_number], ["Venue", m.venue], ["Mode", m.venue_mode],
    ["Time", m.start_time ? `${fmtTime(m.start_time)}${m.end_time ? " – " + fmtTime(m.end_time) : ""}` : null],
    ["Chairperson", m.chairperson], ["Committee", m.committee], ["Financial year", m.financial_year],
    ["Members entitled", m.members_entitled], ["Members attended", m.members_attended], ["Due date", m.due_date ? fmtDate(m.due_date) : null],
  ].filter(([, v]) => v != null && v !== "");
  return items.map(([k, v]) => `<div class="mp-item"><span class="mp-label">${esc(k)}</span><span class="mp-val">${esc(v)}</span></div>`).join("");
}

function card(m) {
  const present = m.attendance.filter((a) => a.attended).length;
  const agenda = m.agenda.length
    ? `<table class="meet-agenda"><thead><tr><th class="ag-num">#</th><th>Agenda item</th></tr></thead><tbody>${m.agenda.map((a) =>
        `<tr><td class="ag-num">${esc(a.item_no)}</td><td class="ag-item">${esc(a.text)}</td></tr>`).join("")}</tbody></table>`
    : `<div class="text-muted small">No agenda recorded.</div>`;
  const att = m.attendance.length
    ? m.attendance.map((a) => `<span class="attend-chip ${a.attended ? "yes" : "no"}" title="${esc(a.mode || "")}">${esc(a.name || a.attendee_type)}${a.mode ? ` · ${esc(a.mode)}` : ""}</span>`).join("")
    : `<span class="text-muted small">No attendance recorded.</span>`;
  const canEdit = canWriteCompany();
  return `<div class="tbl-card meet-card mb-3" data-meeting="${m.id}">
    <div class="meet-head"><div><span class="meet-date">${esc(fmtDate(m.meeting_date))}</span>
        <span class="meet-meta">${esc(m.meeting_type || "")} ${esc(m.meeting_number || "")}</span>
        <span class="pill ${STATUS[m.status] || "pill-na"} ms-2">${esc(m.status)}</span></div>
      <div class="meet-actions no-print">
        ${canEdit ? `<button class="btn btn-sm btn-link" data-act="attendance" type="button">Attendance</button>
        <button class="btn btn-sm btn-link" data-act="upload" type="button">Attach document</button>` : ""}
        <button class="btn btn-sm btn-link" data-act="open" type="button">${canEdit ? "Edit" : "Open"}</button></div></div>
    <div class="meet-particulars">${particulars(m)}</div>
    ${agenda}
    <div class="mt-3"><div class="mp-label mb-1" style="min-width:0">Attendance (${present} of ${m.attendance.length} present)</div>${att}</div>
    ${m.remarks ? `<div class="meet-note">${esc(m.remarks)}</div>` : ""}</div>`;
}

function draw() {
  const canEdit = canWriteCompany();
  $("#view").innerHTML = `<div class="list-bar no-print"><div class="left"><span class="text-muted small">${meetings.length} meeting${meetings.length === 1 ? "" : "s"}</span></div>
      <div class="right">${canEdit ? `<button class="btn btn-sm btn-brand" id="addMeeting" type="button">+ Add meeting</button>` : ""}</div></div>
    ${meetings.length ? meetings.map(card).join("") : `<div class="tbl-card p-5 text-center text-muted">No meetings recorded for this period.</div>`}`;
  const add = $("#addMeeting");
  if (add) add.addEventListener("click", () => openRecord("meeting", null, { onSaved: render }));
  $("#view").onclick = (e) => {
    const btn = e.target.closest("[data-act]");
    if (!btn) return;
    const id = btn.closest("[data-meeting]").dataset.meeting;
    if (btn.dataset.act === "open") openRecord("meeting", id, { onSaved: render });
    else if (btn.dataset.act === "attendance") attendanceDialog(id);
    else if (btn.dataset.act === "upload") {
      openUploadModal({ link: { entity_type: "meeting", entity_id: Number(id), label: "this meeting" }, onDone: render });
    }
  };
}

/* ---------- attendance by roster ---------- */

async function attendanceDialog(id) {
  let m;
  try { m = (await api.get(`/meetings/${id}/detail`)).meeting; } catch (e) { toast(e.message); return; }
  const have = Object.fromEntries(m.attendance.filter((a) => a.directorship_id).map((a) => [a.directorship_id, a]));
  const entry = openModal(`
    <div class="modal-header"><div><div class="rec-title">Attendance — ${esc(fmtDate(m.meeting_date))} ${esc(m.meeting_number || "")}</div>
      <div class="small text-muted">Directors on the board on the day of the meeting. Tick who attended.</div></div>
      <button type="button" class="btn-close" data-close></button></div>
    <div class="modal-body"><div id="atErr"></div>
      ${m.roster.length ? `<table class="table table-sm align-middle"><thead><tr><th style="width:40px"></th><th>Director</th><th>Designation</th><th style="width:170px">Mode</th></tr></thead><tbody>
        ${m.roster.map((r) => `<tr data-did="${r.directorship_id}"><td><input type="checkbox" class="form-check-input" ${have[r.directorship_id] && have[r.directorship_id].attended ? "checked" : ""}></td>
          <td>${esc(r.full_name)}</td><td class="text-muted">${esc(r.designation || "")}</td>
          <td><select class="form-select form-select-sm">${["", "Physical", "VC", "Hybrid"].map((o) => `<option value="${o}" ${(have[r.directorship_id] && have[r.directorship_id].mode) === o ? "selected" : ""}>${o || "—"}</option>`).join("")}</select></td></tr>`).join("")}
        </tbody></table>` : `<div class="text-muted">No directors were on the board on that date.</div>`}</div>
    <div class="modal-footer"><button class="btn btn-outline-secondary" data-close>Cancel</button>
      <button class="btn btn-brand" id="atSave" ${m.roster.length ? "" : "disabled"}>Save attendance</button></div>`);
  entry.el.addEventListener("click", async (e) => {
    if (e.target.closest("[data-close]")) { closeModal(entry); return; }
    if (!e.target.closest("#atSave")) return;
    const rows = Array.from(entry.el.querySelectorAll("tr[data-did]")).map((tr) => ({
      directorship_id: Number(tr.dataset.did), attended: tr.querySelector("input").checked, mode: tr.querySelector("select").value || null }));
    try {
      const res = await api.put(`/meetings/${id}/attendance`, { rows });
      toast(`Attendance saved — ${res.attended} present`);
      closeModal(entry);
      render();
    } catch (err) { entry.el.querySelector("#atErr").innerHTML = `<div class="rec-error">${esc(err.message)}</div>`; }
  });
}
