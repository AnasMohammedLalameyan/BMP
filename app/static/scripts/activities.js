/* Activities & Tasks - the Activity Database in use.

   An activity (here: a Board Meeting) is a recipe of ordered steps. Starting one for a company creates a task
   per step with due dates worked out from the meeting date. Each task shows what it reads and writes in the
   records, the evidence it needs, and moves through its status under the rules the database cannot express
   alone: earlier steps first, and a named person's confirmation where the step requires it. */

import * as api from "./api.js";
import { canWriteCompany, company, state } from "./state.js";
import { $, esc, fmtDate, fmtDateTime, pillClass, toast, words } from "./util.js";
import { openRecord } from "./entity.js";
import { openUploadModal } from "./documents.js";
import { renderStartFields, collectParams, clearFieldErrors, showFieldErrors } from "./activity-form.js";

let templates = [];
let instances = [];
let openId = null;
let notify = null;

export async function render(onChange) {
  notify = onChange;
  const co = company();
  $("#crumb").textContent = "";
  $("#pageTitle").textContent = "Activities & Tasks";
  $("#pageSub").innerHTML = `${esc(co ? co.name : "")} &middot; <span class="text-muted">step-by-step compliance activities with due dates, evidence and confirmations</span>`;
  $("#view").innerHTML = `<div class="tbl-card p-4 text-muted">Loading…</div>`;
  try {
    templates = (await api.get("/activities/templates")).templates;
    instances = (await api.get(`/companies/${state.companyId}/activities`)).instances;
  } catch (e) { $("#view").innerHTML = `<div class="tbl-card p-4 text-danger">${esc(e.message)}</div>`; return; }
  if (openId) await showInstance(openId); else drawList();
}

/* ================= list: start + running activities + templates ================= */

function paramsSummary(p) {
  if (!p) return "";
  return [p.meeting_date ? fmtDate(p.meeting_date) : null, p.venue_mode, p.venue].filter(Boolean).join(" · ");
}

function drawList() {
  openId = null;
  const canStart = canWriteCompany();
  $("#view").innerHTML = `
    ${canStart ? `<div class="tbl-card p-3 mb-3 no-print"><div class="fw-bold text-brand mb-2">Start an activity</div>
      <div class="d-flex gap-2 flex-wrap align-items-end">
        <div><label class="form-label small text-muted mb-1">Activity</label>
          <select class="form-select form-select-sm" id="tplSel" style="min-width:300px">${templates.map((t) =>
            `<option value="${esc(t.code)}" data-id="${t.id}">${esc(t.name)} (v${t.version}${t.status === "draft" ? ", draft" : ""})</option>`).join("")}</select></div>
        <button class="btn btn-brand btn-sm" id="tplStart" type="button">Set up…</button></div>
      <div id="startForm" class="mt-3"></div></div>` : ""}
    <h2 class="h6 fw-bold text-brand mb-2">This company's activities</h2>
    ${instances.length ? instances.map((i) => {
      const pct = i.tasks ? Math.round((i.done / i.tasks) * 100) : 0;
      return `<div class="tbl-card p-3 mb-3 grp-card" data-open-instance="${i.id}" role="button">
        <div class="d-flex align-items-center gap-2 flex-wrap">
          <div><div class="fw-bold text-brand">${esc(i.name)} <span class="text-muted fw-normal">#${i.id}</span></div>
            <div class="text-muted" style="font-size:.78rem">${esc(paramsSummary(i.params))}</div></div>
          <span class="ms-auto pill ${pillClass(i.status)}">${esc(i.status)}</span>
          ${i.overdue ? `<span class="pill pill-no">${i.overdue} overdue</span>` : ""}</div>
        <div class="progress my-2" style="height:.5rem"><div class="progress-bar" style="width:${pct}%;background:var(--brand-2)"></div></div>
        <div class="text-muted" style="font-size:.76rem">${i.done} of ${i.tasks} tasks done${i.next_due ? ` · next due ${esc(fmtDate(i.next_due))}` : ""} · started by ${esc(i.created_by_name || "—")} on ${esc(fmtDateTime(i.created_at))}</div></div>`;
    }).join("") : `<div class="tbl-card p-4 text-muted mb-3">No activities started for this company yet.</div>`}
    <h2 class="h6 fw-bold text-brand mb-2 mt-4">Activity definitions</h2>
    ${templates.map((t) => `<div class="tbl-card p-3 mb-3"><div class="d-flex align-items-center gap-2 flex-wrap">
        <div><div class="fw-bold text-brand">${esc(t.name)} <span class="text-muted fw-normal">v${t.version}</span></div>
          <div class="text-muted" style="font-size:.78rem">${esc(t.obligation_ref || "")}</div></div>
        <span class="ms-auto pill ${pillClass(t.status)}">${esc(t.status)}</span>
        <span class="pill pill-na">${t.steps} steps</span>
        <button class="btn btn-sm btn-outline-brand" data-view-template="${t.id}" type="button">View steps</button></div>
        ${t.status === "draft" ? `<div class="rec-note mt-2">Draft — the step durations are defaults from the Companies Act (s.173) and Secretarial Standard SS-1 and have not yet been verified by a BMP professional.</div>` : ""}
        <div id="tpl_${t.id}"></div></div>`).join("")}`;
  if (canStart) {
    $("#tplStart").addEventListener("click", () => startForm());
    if (templates.length) startForm();
  }
  $("#view").onclick = (e) => {
    const open = e.target.closest("[data-open-instance]");
    if (open) { showInstance(Number(open.dataset.openInstance)); return; }
    const vt = e.target.closest("[data-view-template]");
    if (vt) toggleTemplate(Number(vt.dataset.viewTemplate));
  };
}

async function toggleTemplate(id) {
  const host = $(`#tpl_${id}`);
  if (host.innerHTML) { host.innerHTML = ""; return; }
  try {
    const { template, steps } = await api.get(`/activities/templates/${id}`);
    host.innerHTML = `<div class="table-responsive mt-3"><table class="table chk-table align-middle mb-0"><thead><tr><th>#</th><th>Step</th><th>Type</th><th>Responsible</th><th>Deadline</th><th>Reads / writes</th><th>Evidence</th></tr></thead><tbody>
      ${steps.map((s) => `<tr><td>${s.seq}</td><td><div class="fw-semibold">${esc(s.title)}</div><div class="co-sub">${esc(s.instructions || "")}</div>
        ${s.depends_on.length ? `<div class="co-sub">After step ${s.depends_on.map((d) => (steps.find((x) => x.id === d) || {}).seq).join(", ")}</div>` : ""}
        ${s.requires_confirmation ? '<span class="flag-chip">needs confirmation</span>' : ""}${s.ai_assisted ? '<span class="flag-chip">AI-assisted (later phase)</span>' : ""}</td>
        <td><span class="pill pill-na">${esc(words(s.step_type))}</span></td><td>${esc(s.responsible_role || "—")}</td><td>${esc(s.deadline || "—")}</td>
        <td>${s.bindings.map((b) => `<span class="bind-chip bind-${b.mode}" title="${esc(b.mode)}">${esc(b.table_name.replace("core.", ""))}.${esc(b.column_name)}</span>`).join("") || "—"}</td>
        <td>${s.evidence.map((x) => `<span class="ag-chip ag-doc">${esc(x.document_type)}${x.is_mandatory ? " *" : ""}</span>`).join("") || "—"}</td></tr>`).join("")}</tbody></table></div>
      <div class="text-muted mt-1" style="font-size:.72rem">* mandatory evidence &middot; green = the step writes this field, blue = it only reads it</div>`;
  } catch (e) { toast(e.message); }
}

/* ---------- the start form, generated from the template's input_schema ---------- */

function startForm() {
  const tpl = templates.find((t) => t.code === $("#tplSel").value);
  if (!tpl) return;
  const host = $("#startForm");
  host.innerHTML = `<div id="startFieldsHost"></div>
    <div class="text-danger small mt-2" id="startErr"></div>
    <button class="btn btn-brand btn-sm mt-2" id="startGo" type="button">Start activity</button>`;
  const fieldsHost = $("#startFieldsHost");
  renderStartFields(fieldsHost, tpl);
  $("#startGo").addEventListener("click", async () => {
    const params = collectParams(fieldsHost);
    clearFieldErrors(fieldsHost);
    $("#startErr").textContent = "";
    try {
      const detail = await api.post("/activities/instances", { template_code: tpl.code, company_id: state.companyId, params });
      toast(`Started: ${detail.tasks.length} tasks created`);
      openId = detail.instance.id;
      instances = (await api.get(`/companies/${state.companyId}/activities`)).instances;
      draw(detail);
      if (notify) notify();
    } catch (err) {
      $("#startErr").textContent = err.message;
      showFieldErrors(fieldsHost, err);
    }
  });
}

/* ================= one activity: the task board ================= */

async function showInstance(id) {
  openId = id;
  try { draw(await api.get(`/activities/instances/${id}`)); }
  catch (e) { toast(e.message); openId = null; drawList(); }
}

function actionButtons(k, canEdit) {
  if (!canEdit || k.step === undefined) return "";
  const b = (status, label, cls) => `<button class="btn btn-sm ${cls}" data-task-status="${status}" type="button">${label}</button>`;
  if (k.status === "not_started") return b("in_progress", "Start", "btn-outline-brand") + b("completed", "Mark complete", "btn-brand") + b("skipped", "Skip", "btn-outline-secondary");
  if (k.status === "in_progress") return b("completed", "Mark complete", "btn-brand") + b("skipped", "Skip", "btn-outline-secondary") + b("not_started", "Back", "btn-outline-secondary");
  return b("not_started", "Reopen", "btn-outline-secondary");
}

function draw(detail) {
  const { instance: inst, tasks } = detail;
  const canEdit = canWriteCompany() && inst.status !== "cancelled";
  const done = tasks.filter((t) => ["completed", "skipped"].includes(t.status)).length;
  const pct = tasks.length ? Math.round((done / tasks.length) * 100) : 0;
  $("#view").innerHTML = `
    <div class="mb-3 no-print"><a role="button" class="crumb-link" id="backToList">&larr; All activities</a></div>
    <div class="tbl-card p-3 mb-3">
      <div class="d-flex align-items-center gap-2 flex-wrap">
        <div><div class="fw-bold text-brand fs-5">${esc(inst.template_name)} <span class="text-muted fw-normal">#${inst.id}</span></div>
          <div class="text-muted" style="font-size:.8rem">${esc(paramsSummary(inst.params))}</div></div>
        <span class="ms-auto pill ${pillClass(inst.status)}">${esc(inst.status)}</span>
        ${canWriteCompany() ? (inst.status === "cancelled"
          ? `<button class="btn btn-sm btn-outline-brand" data-inst-status="active" type="button">Reopen activity</button>`
          : inst.status === "active" ? `<button class="btn btn-sm btn-outline-danger" data-inst-status="cancelled" type="button">Cancel activity</button>` : "") : ""}</div>
      <div class="progress my-2" style="height:.55rem"><div class="progress-bar" style="width:${pct}%;background:var(--brand-2)"></div></div>
      <div class="text-muted" style="font-size:.78rem">${done} of ${tasks.length} tasks done</div>
      ${inst.template_status === "draft" ? `<div class="rec-note mt-2">This activity follows a <b>draft</b> definition awaiting professional review.</div>` : ""}
      ${inst.params && inst.params.agenda_items && inst.params.agenda_items.length ? `<details class="mt-2"><summary class="text-muted small" style="cursor:pointer">Agenda items entered when the activity was started</summary>
        <ol class="small mt-1 mb-0">${inst.params.agenda_items.map((a) => `<li>${esc(a)}</li>`).join("")}</ol></details>` : ""}</div>
    <div id="warnBox"></div>
    ${tasks.map((k) => taskCard(k, canEdit)).join("")}`;
  $("#backToList").addEventListener("click", () => { openId = null; render(notify); });
  $("#view").onclick = (e) => onClick(e, tasks, inst);
  if (detail.warnings && detail.warnings.length) $("#warnBox").innerHTML = `<div class="rec-note mb-3">${detail.warnings.map(esc).join("<br>")}</div>`;
}

function taskCard(k, canEdit) {
  const s = k.step;
  const needsConf = s.requires_confirmation;
  const pending = k.confirmations.find((c) => c.status === "pending");
  return `<div class="task-card ${["completed", "skipped"].includes(k.status) ? "done" : ""} ${k.is_overdue ? "overdue" : ""}" data-task="${k.id}">
    <div class="task-head"><span class="task-seq">${s.seq}</span>
      <div><div class="task-title">${esc(s.title)}</div>
        <div class="text-muted" style="font-size:.72rem">${esc(words(s.step_type))} · ${esc(s.responsible_role || "—")}${s.is_mandatory ? "" : " · optional"}</div></div>
      <span class="ms-auto pill ${k.is_overdue ? "pill-no" : pillClass(k.status)}">${esc(k.is_overdue ? "overdue" : words(k.status))}</span>
      <div class="d-flex gap-1 no-print">${actionButtons(k, canEdit)}</div></div>
    <div class="task-body">
      <div class="task-meta"><span>Due: <b>${k.due_date ? esc(fmtDate(k.due_date)) : "no fixed date"}</b>${s.deadline ? ` (${esc(s.deadline)})` : ""}</span>
        ${k.completed_at ? `<span>Completed by <b>${esc(k.completed_by_name || "—")}</b> on ${esc(fmtDateTime(k.completed_at))}</span>` : ""}
        ${needsConf ? '<span class="flag-chip">needs a named person\'s confirmation</span>' : ""}</div>
      ${s.instructions ? `<div class="mb-2">${esc(s.instructions)}</div>` : ""}
      ${k.blocked_by.length && !["completed", "skipped"].includes(k.status) ? `<div class="task-block">Waiting for: ${k.blocked_by.map(esc).join("; ")}</div>` : ""}
      ${s.bindings.length ? `<div class="mb-2"><span class="text-muted small">Uses these records: </span>${s.bindings.map((b) =>
        `<span class="bind-chip bind-${b.mode}" title="${b.mode === "write" ? "this step writes it" : "this step reads it"}">${esc(b.table_name.replace("core.", ""))}.${esc(b.column_name)}</span>`).join("")}</div>` : ""}
      ${(s.evidence.length || k.evidence.length) ? `<div class="mb-2"><span class="text-muted small">Evidence: </span>
        ${s.evidence.map((e) => { const got = k.evidence.some((x) => x.document_type === e.document_type);
          return `<span class="ag-chip ${got ? "ag-reg" : "ag-form"}">${got ? "✓ " : ""}${esc(e.document_type)}${e.is_mandatory ? " *" : ""}</span>`; }).join("")}
        ${k.evidence.map((x) => `<a role="button" class="small ms-2" data-download="${x.document_id}" data-name="${esc(x.filename)}">${esc(x.filename)} (v${x.version})</a>`).join("")}
        ${canEdit ? `<button class="btn btn-sm btn-link p-0 ms-2 no-print" data-attach="${k.id}" type="button">Attach evidence</button>` : ""}</div>` : (canEdit ? `<button class="btn btn-sm btn-link p-0 no-print" data-attach="${k.id}" type="button">Attach evidence</button>` : "")}
      ${k.links.length ? `<div class="mb-2"><span class="text-muted small">Records this task involved: </span>${k.links.map((l) =>
        `<span class="ag-chip ag-reg" title="${esc(l.mode)}">${esc(l.entity_type)} · ${esc((l._labels && l._labels.entity_id) || "#" + l.entity_id)} (${esc(l.mode)})</span>`).join("")}</div>` : ""}
      ${canEdit ? `<button class="btn btn-sm btn-link p-0 no-print" data-link="${k.id}" type="button">Link a record</button>` : ""}
      ${needsConf ? `<div class="mt-2"><span class="text-muted small">Confirmation: </span>
        ${k.confirmations.map((c) => `<span class="pill ${pillClass(c.status)} me-1">${esc(c.status)}${c.confirmed_by_name ? " by " + esc(c.confirmed_by_name) : ` · asked by ${esc(c.requested_by_name || "—")}`}</span>
          ${c.status === "pending" && canEdit ? `<button class="btn btn-sm btn-outline-brand" data-decide="confirm" data-conf="${c.id}" type="button">Confirm</button>
            <button class="btn btn-sm btn-outline-secondary" data-decide="reject" data-conf="${c.id}" type="button">Reject</button>` : ""}`).join("") || '<span class="muted-dash">none requested</span>'}
        ${canEdit && !pending && !k.confirmed && !["completed", "skipped"].includes(k.status) ? `<button class="btn btn-sm btn-outline-brand ms-1" data-request-conf="${k.id}" type="button">Request confirmation</button>` : ""}</div>` : ""}
      <div class="mt-2"><textarea class="form-control form-control-sm" rows="1" data-notes="${k.id}" data-version="${esc(k.updated_at)}" placeholder="Notes…" ${canEdit ? "" : "disabled"}>${esc(k.notes || "")}</textarea></div>
    </div></div>`;
}

async function onClick(e, tasks, inst) {
  const act = async (fn) => {
    try { draw(await fn()); if (notify) notify(); }
    catch (err) { toast(err.message); }
  };
  const statusBtn = e.target.closest("[data-task-status]");
  if (statusBtn) {
    const id = statusBtn.closest("[data-task]").dataset.task;
    await act(() => api.post(`/activities/tasks/${id}/status`, { status: statusBtn.dataset.taskStatus }));
    return;
  }
  const instBtn = e.target.closest("[data-inst-status]");
  if (instBtn) {
    if (instBtn.dataset.instStatus === "cancelled" && !window.confirm("Cancel this activity? Its tasks are kept for the record, and you can reopen it later.")) return;
    await act(() => api.post(`/activities/instances/${inst.id}/status`, { status: instBtn.dataset.instStatus }));
    return;
  }
  const req = e.target.closest("[data-request-conf]");
  if (req) {
    try { await api.post(`/activities/tasks/${req.dataset.requestConf}/confirmations`, {}); toast("Confirmation requested"); await showInstance(inst.id); }
    catch (err) { toast(err.message); }
    return;
  }
  const dec = e.target.closest("[data-decide]");
  if (dec) {
    try { await api.post(`/confirmations/${dec.dataset.conf}/${dec.dataset.decide}`, {}); toast(dec.dataset.decide === "confirm" ? "Confirmed" : "Rejected"); await showInstance(inst.id); }
    catch (err) { toast(err.message); }
    return;
  }
  const attach = e.target.closest("[data-attach]");
  if (attach) {
    openUploadModal({ companyId: inst.company_id, link: { entity_type: "task_instance", entity_id: Number(attach.dataset.attach), task_instance_id: Number(attach.dataset.attach), label: "this task" },
      onDone: () => showInstance(inst.id) });
    return;
  }
  const link = e.target.closest("[data-link]");
  if (link) {
    openRecord("task_record_link", null, { defaults: { task_instance_id: Number(link.dataset.link) }, fixed: ["task_instance_id"], labels: {}, onSaved: () => showInstance(inst.id) });
    return;
  }
  const dl = e.target.closest("[data-download]");
  if (dl) api.download(`/documents/${dl.dataset.download}/download`, {}, dl.dataset.name).catch((err) => toast(err.message));
}

// notes save when the box loses focus
document.addEventListener("change", async (e) => {
  const box = e.target.closest("[data-notes]");
  if (!box) return;
  try {
    await api.updateRecord("task_instance", box.dataset.notes, { notes: box.value, updated_at: box.dataset.version });
    toast("Note saved");
    if (openId) showInstance(openId);
  } catch (err) { toast(err.message); }
});
