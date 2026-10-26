/* AI elements of the Activities Dashboard. Everything here only SUGGESTS or DRAFTS: values land in the open form for the
   person to review, and saving or sending stays with the normal Save and the explicit approval step.
   Hidden completely when the server says AI is off. Only plain labels are shown, never record ids or database names. */

import * as api from "./api.js";
import { matchRoster } from "./act-form.js";
import { canWriteCompany, state } from "./state.js";
import { $, esc, toast } from "./util.js";

let status = { enabled: false };
const FRIENDLY = "AI is unavailable right now. You can continue by hand.";

export async function loadStatus() {
  try { status = await api.get("/ai/status"); } catch (e) { status = { enabled: false }; }
  return status.enabled;
}
export const enabled = () => !!status.enabled;

const fail = (e) => toast(e && (e.status === 503 || e.status === 0) ? FRIENDLY : ((e && e.message) || FRIENDLY));

/* ---------------------------------------------------------------- a small dialog of our own ---- */

let dialogEl = null;
function dialog(title, bodyHTML, footerHTML) {
  if (!dialogEl) {
    dialogEl = document.createElement("div");
    dialogEl.className = "modal fade";
    dialogEl.tabIndex = -1;
    dialogEl.innerHTML = `<div class="modal-dialog modal-lg modal-dialog-scrollable"><div class="modal-content">
      <div class="modal-header"><h5 class="modal-title" id="aiDlgTitle"></h5><button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button></div>
      <div class="modal-body" id="aiDlgBody"></div><div class="modal-footer" id="aiDlgFoot"></div></div></div>`;
    $("#modalHost").appendChild(dialogEl);
  }
  $("#aiDlgTitle").textContent = title;
  $("#aiDlgBody").innerHTML = bodyHTML;
  $("#aiDlgFoot").innerHTML = footerHTML || `<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Close</button>`;
  const m = window.bootstrap.Modal.getOrCreateInstance(dialogEl);
  m.show();
  return m;
}
const closeDialog = () => dialogEl && window.bootstrap.Modal.getOrCreateInstance(dialogEl).hide();

/* ---------------------------------------------------------------- what the register view mounts ---- */

/** In the add/edit panel: "Describe it instead" (new meetings only) and "Suggest from document". */
export function mountPanel(host, isNew) {
  const slot = $("#aiSlot");
  if (!slot || !enabled()) return;
  slot.innerHTML = `<div class="ai-box no-print">
    ${isNew ? `<div class="ai-describe"><label class="form-label small mb-1">Describe it instead</label>
      <div class="d-flex gap-2"><input class="form-control form-control-sm" id="aiDescribe" maxlength="1500"
        placeholder="e.g. Board meeting of BrightMed on 12 June 2026 at 11 AM, by video conferencing, to approve the accounts">
      <button type="button" class="btn btn-sm btn-outline-brand" data-meet-action="ai-describe">Fill the form</button></div></div>` : ""}
    <div class="mt-2"><button type="button" class="btn btn-sm btn-outline-brand" data-meet-action="ai-suggest">Suggest from document</button>
      <span class="small text-muted ms-2" id="aiNote"></span></div></div>`;
}

export const noticeButton = () => (enabled() && canWriteCompany()
  ? `<button class="btn btn-sm btn-link" type="button" data-meet-action="ai-notice">Draft notice</button>` : "");

/** On a register's list: the Ask box. */
export function mountAsk(reg) {
  const slot = $("#aiAskSlot");
  if (!slot || !enabled()) return;
  slot.innerHTML = `<div class="tbl-card p-3 mb-3 no-print ai-ask"><label class="form-label small mb-1">Ask about these meetings or the law</label>
    <div class="d-flex gap-2"><input class="form-control form-control-sm" id="aiQuestion" maxlength="500"
      placeholder="e.g. What notice period does a board meeting need?">
      <button type="button" class="btn btn-sm btn-brand" data-meet-action="ai-ask">Ask</button></div>
    <div id="aiAnswer" class="mt-2 small"></div></div>`;
  $("#aiQuestion").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); ask(reg); } });
}

export async function handle(act, btn, host) {
  if (act === "ai-describe") return describe(host);
  if (act === "ai-suggest") return suggestStart(host);
  if (act === "ai-notice") {
    const id = Number(btn.closest("[data-meeting]").dataset.meeting);
    return noticeDraft(host, id);
  }
  if (act === "ai-ask") return ask(host.register());
  return undefined;
}

/* ---------------------------------------------------------------- describe it instead ---- */

async function describe(host) {
  const text = $("#aiDescribe").value.trim();
  const note = $("#aiNote");
  if (!text) { toast("Please describe the meeting first."); return; }
  note.textContent = "Reading…";
  let res;
  try { res = await api.post("/ai/intake", { text, company_id: state.companyId }); }
  catch (e) { note.textContent = ""; fail(e); return; }
  if (res.kind !== "intake") { note.textContent = res.message || ""; return; }
  if (res.register && res.register !== host.register()) {
    note.textContent = "This sounds like a different kind of meeting. Open that register and describe it there.";
    return;
  }
  host.capture();
  const d = host.draft();
  Object.entries(res.fields || {}).forEach(([k, v]) => { if (v) d[k] = v; });
  if (res.agenda && res.agenda.length) {
    d.agenda = res.agenda.map((t) => ({ id: null, text: t, reg30: "NA", forms: "", docs: "", comments: "" }));
  }
  if (res.fields && res.fields.meeting_date) await host.reloadRoster();
  host.redraw();
  const notes = [];
  if (res.question) notes.push(res.question);
  if (res.missing && res.missing.length) notes.push("Still needed: " + res.missing.join("; ") + ".");
  $("#aiNote").textContent = notes.join(" ") || "Filled in for you to review. Nothing is saved until you press Save.";
}

/* ---------------------------------------------------------------- suggest from document ---- */

async function suggestStart(host) {
  let docs;
  try { docs = (await api.get("/ai/documents", { company_id: state.companyId })).documents; }
  catch (e) { fail(e); return; }
  if (!docs.length) { toast("No documents are stored for this company yet."); return; }
  dialog("Suggest from a document", `<p class="small text-muted">Pick a stored minutes or notice. The assistant reads it and suggests details
    for you to review; nothing is changed until you apply them and press Save.</p>
    <select class="form-select" id="aiDoc">${docs.map((d) => `<option value="${d.id}">${esc(d.name)}</option>`).join("")}</select>
    <div id="aiSuggestOut" class="mt-3"></div>`,
  `<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancel</button>
   <button type="button" class="btn btn-brand" id="aiRead">Read document</button>`);
  $("#aiRead").onclick = () => suggestRun(host);
}

const TIER = { high: ["High", "bs-ok"], check: ["Please check", "bs-na"], unverified: ["Unverified", "bs-no"] };

async function suggestRun(host) {
  const out = $("#aiSuggestOut");
  host.capture();
  const d = host.draft();
  out.innerHTML = `<div class="text-muted">Reading…</div>`;
  $("#aiRead").disabled = true;
  let res;
  try {
    res = await api.post("/ai/suggest", { company_id: state.companyId, document_id: Number($("#aiDoc").value),
      meeting_id: d.meeting_id || undefined });
  } catch (e) { out.innerHTML = `<div class="text-danger">${esc(e.status === 422 ? e.message : (e.status === 503 ? FRIENDLY : e.message))}</div>`; $("#aiRead").disabled = false; return; }
  if (!res.fields.length && !res.agenda.length) { out.innerHTML = `<div class="text-muted">Nothing could be read with confidence from this document.</div>`; $("#aiRead").disabled = false; return; }
  const emptyAgenda = d.agenda.every((a) => !String(a.text || "").trim());
  const rows = res.fields.map((f, i) => {
    const [label, cls] = TIER[f.tier] || TIER.check;
    return `<tr><td><input type="checkbox" class="form-check-input" data-sf="${i}" ${f.conflict || f.tier === "unverified" ? "" : "checked"}></td>
      <td>${esc(f.label)}</td><td class="text-muted">${esc(f.current || "—")}</td><td><strong>${esc(f.proposed)}</strong>
      ${f.conflict ? `<div class="small text-danger">Different from what is recorded</div>` : ""}</td>
      <td><span class="badge-soft ${cls}">${label}</span></td><td class="small text-muted">“${esc(f.quote)}”, page ${f.page}</td></tr>`;
  }).join("");
  const agenda = res.agenda.length ? `<div class="form-check my-2"><input type="checkbox" class="form-check-input" id="sfAgenda" ${emptyAgenda ? "checked" : ""}>
    <label class="form-check-label" for="sfAgenda">Replace the agenda with these ${res.agenda.length} item(s)</label></div>
    <ol class="small">${res.agenda.map((a) => `<li>${esc(a.text)} <span class="text-muted">(page ${a.page})</span></li>`).join("")}</ol>` : "";
  out.innerHTML = `<table class="table table-sm align-middle"><thead><tr><th></th><th>Detail</th><th>Now</th><th>Suggested</th><th>Confidence</th><th>From the document</th></tr></thead>
    <tbody>${rows}</tbody></table>${agenda}
    <button type="button" class="btn btn-brand" id="aiApply">Apply selected to the form</button>`;
  $("#aiApply").onclick = async () => {
    const picked = $("#aiSuggestOut").querySelectorAll("[data-sf]");
    let reload = false;
    picked.forEach((cb) => {
      if (!cb.checked) return;
      const f = res.fields[Number(cb.dataset.sf)];
      if (f.key === "directors_present") return;                   // handled below through the roster
      d[f.key] = f.proposed;
      if (f.key === "meeting_date") reload = true;
    });
    if (reload) await host.reloadRoster();
    picked.forEach((cb) => {
      const f = res.fields[Number(cb.dataset.sf)];
      if (cb.checked && f.key === "directors_present") {
        matchRoster(f.proposed, host.roster()).matched.forEach((id) => d.ticked.add(id));
        d._presentTouched = false;
      }
    });
    const ag = $("#sfAgenda");
    if (ag && ag.checked) {
      d.agenda = res.agenda.map((a) => ({ id: null, text: a.text, reg30: "NA", forms: a.forms, docs: a.docs, comments: "" }));
    }
    closeDialog();
    host.redraw();
    $("#aiNote").textContent = "Suggestions applied for you to review. Nothing is saved until you press Save.";
  };
}

/* ---------------------------------------------------------------- draft and send a notice ---- */

async function noticeDraft(host, meetingId) {
  dialog("Draft notice", `<div class="text-muted">Preparing the notice…</div>`, `<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Close</button>`);
  let res;
  try { res = await api.post(`/ai/meetings/${meetingId}/${host.register()}/notice/draft`); }
  catch (e) { $("#aiDlgBody").innerHTML = `<div class="text-danger">${esc(e.status === 503 ? FRIENDLY : e.message)}</div>`; return; }
  const blocked = res.missing.length > 0;
  $("#aiDlgBody").innerHTML = `
    ${res.sandbox ? `<div class="alert alert-info py-2 small">Test mode: messages go to the local test mail server only, not to real inboxes.</div>` : ""}
    ${blocked ? `<div class="alert alert-warning py-2 small">Details still missing, so this cannot be sent yet: ${esc(res.missing.join(", "))}.</div>` : ""}
    <div class="small text-muted">Subject</div><div class="mb-2"><strong>${esc(res.subject)}</strong></div>
    <label class="form-label small mb-1">Covering message (you can edit it; the name is filled in for each person)</label>
    <textarea class="form-control form-control-sm mb-2" rows="4" id="aiCover">${esc(res.cover)}</textarea>
    <div class="small text-muted">Notice</div><pre class="ai-notice">${esc(res.notice)}</pre>
    <div class="small text-muted mt-2">Recipients (${res.recipients.length})</div>
    <table class="table table-sm"><tbody>${res.recipients.map((r) => `<tr><td>${esc(r.name)}</td><td class="text-muted">${esc(r.role)}</td>
      <td>${r.has_email ? esc(r.email) : `<span class="text-danger">no email address</span>`}</td></tr>`).join("")}</tbody></table>
    <div class="form-check mt-2"><input type="checkbox" class="form-check-input" id="aiApprove" ${blocked ? "disabled" : ""}>
      <label class="form-check-label" for="aiApprove">I have read this notice and approve sending it to the recipients above.</label></div>
    <div id="aiSendOut" class="mt-2 small"></div>`;
  $("#aiDlgFoot").innerHTML = `<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Close</button>
    <button type="button" class="btn btn-brand" id="aiSend" disabled>Approve and send</button>`;
  const send = $("#aiSend");
  $("#aiApprove").addEventListener("change", (e) => { send.disabled = !e.target.checked || blocked; });
  send.onclick = async () => {
    send.disabled = true;                                           // one click only
    $("#aiApprove").disabled = true;
    try {
      const out = await api.post(`/ai/meetings/${meetingId}/${host.register()}/notice/send`,
        { approve: true, cover: $("#aiCover").value, fingerprint: res.fingerprint });
      const label = { sent: "Sent", no_email: "No email address", failed: "Could not be sent" };
      $("#aiSendOut").innerHTML = `<strong>${out.sent} of ${out.results.length} sent.</strong><ul>${out.results.map((r) =>
        `<li>${esc(r.name)}: ${label[r.status] || esc(r.status)}</li>`).join("")}</ul>`;
    } catch (e) { $("#aiSendOut").innerHTML = `<div class="text-danger">${esc(e.message)}</div>`; }
  };
}

/* ---------------------------------------------------------------- ask ---- */

async function ask(register) {
  const q = $("#aiQuestion").value.trim();
  const out = $("#aiAnswer");
  if (!q) return;
  out.textContent = "Looking…";
  let res;
  try { res = await api.post(`/ai/${register}/ask`, { company_id: state.companyId, question: q }); }
  catch (e) { out.innerHTML = `<span class="text-danger">${esc(e.code === "ask_unavailable" ? "Questions are unavailable right now." : (e.status === 503 ? FRIENDLY : e.message))}</span>`; return; }
  if (res.declined) { out.textContent = res.message; return; }
  out.innerHTML = res.answer.map((c) => `<div class="mb-1">${esc(c.text)} <span class="text-muted">[${esc(c.citation)}]</span></div>`).join("")
    + (res.note ? `<div class="text-muted mt-1">${esc(res.note)}</div>` : "")
    + (res.library ? "" : `<div class="text-muted mt-1">No statute library is loaded: answers come from the company's documents only.</div>`);
}
