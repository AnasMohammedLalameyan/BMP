/* Documents & Evidence: upload a file (drag and drop or browse), tie it to a record or a task, find it again.

   The server fingerprints each file (SHA-256), versions repeated uploads of the same name, stores it outside the
   database, and records an evidence link - the durable connection from a document to the thing it proves. */

import * as api from "./api.js";
import { canWriteCompany, company, entityMeta, state } from "./state.js";
import { $, esc, toast, wireDropzone } from "./util.js";
import { closeModal, mountList, openModal } from "./entity.js";
import { hydrateFk } from "./form.js";

/** The upload dialog. `link` may carry {entity_type, entity_id, task_instance_id, label} when opened from a record. */
export function openUploadModal({ companyId, link, onDone } = {}) {
  const cid = companyId || state.companyId;
  let file = null;
  const entry = openModal(`
    <div class="modal-header"><div><div class="rec-title">Upload a document</div>
      <div class="small text-muted">${link && link.label ? "Will be linked to: " + esc(link.label) : "Stored against the open company."}</div></div>
      <button type="button" class="btn-close" data-close></button></div>
    <div class="modal-body"><div id="upErr"></div>
      <input type="file" id="upFile" hidden>
      <div class="file-drop mb-3" id="upDrop" role="button" title="Drag a file here, or click to browse">
        <div style="font-size:1.4rem">&#8595;</div><div class="fw-semibold" id="upName">Drag &amp; drop a file here</div>
        <div class="text-muted small mt-1">PDF, Word, Excel, CSV, text or image — or click to browse</div></div>
      <div class="rec-grid">
        <div class="rec-field"><label>Document type</label><select class="form-select form-select-sm" id="upType" data-fk="document_type" data-selected=""><option value="">—</option></select></div>
        <div class="rec-field wide"><label>Note (optional)</label><input class="form-control form-control-sm" id="upNote"></div></div>
    </div>
    <div class="modal-footer"><button class="btn btn-outline-secondary" data-close>Cancel</button>
      <button class="btn btn-brand" id="upGo" disabled>Upload</button></div>`);
  hydrateFk(entry.el.querySelector("#upType").parentElement, null);
  const input = entry.el.querySelector("#upFile");
  const pick = (f) => { file = f; entry.el.querySelector("#upName").textContent = f.name; entry.el.querySelector("#upGo").disabled = false; };
  entry.el.querySelector("#upDrop").addEventListener("click", () => input.click());
  input.addEventListener("change", () => { if (input.files[0]) pick(input.files[0]); });
  wireDropzone(entry.el.querySelector("#upDrop"), (files) => pick(files[0]));
  entry.el.addEventListener("click", async (e) => {
    if (e.target.closest("[data-close]")) { closeModal(entry); return; }
    if (!e.target.closest("#upGo") || !file) return;
    const form = new FormData();
    form.append("company_id", cid);
    form.append("file", file);
    const type = entry.el.querySelector("#upType").value;
    if (type) form.append("document_type_id", type);
    if (link && link.entity_type) { form.append("entity_type", link.entity_type); form.append("entity_id", link.entity_id); }
    if (link && link.task_instance_id) form.append("task_instance_id", link.task_instance_id);
    const note = entry.el.querySelector("#upNote").value.trim();
    if (note) form.append("note", note);
    const btn = entry.el.querySelector("#upGo");
    btn.disabled = true;
    try {
      const res = await api.upload("/documents/upload", form);
      toast(`Uploaded ${res.document.filename} (version ${res.document.version})`);
      closeModal(entry);
      if (onDone) onDone(res);
    } catch (err) {
      entry.el.querySelector("#upErr").innerHTML = `<div class="rec-error">${esc(err.message)}</div>`;
      btn.disabled = false;
    }
  });
}

export function render() {
  const co = company();
  $("#crumb").textContent = "";
  $("#pageTitle").textContent = "Documents & Evidence";
  $("#pageSub").innerHTML = `${esc(co ? co.name : "")} &middot; <span class="text-muted">files are fingerprinted, versioned and linked to the records and tasks they prove</span>`;
  const canUp = canWriteCompany();
  $("#view").innerHTML = `${canUp ? `<div class="tbl-card p-3 mb-3 d-flex justify-content-between align-items-center flex-wrap gap-2 no-print" id="docDrop">
      <div><div class="fw-semibold text-brand">Add evidence</div>
        <div class="text-muted small">Drop a file anywhere on this card, or use the button.</div></div>
      <button class="btn btn-brand" id="docUpload" type="button">&#8593; Upload a document</button></div>` : ""}
    <div id="docList"></div>`;
  const ctl = mountList($("#docList"), "document", { size: 15, useFy: false });
  if (canUp) {
    $("#docUpload").addEventListener("click", () => openUploadModal({ onDone: () => ctl.reload() }));
    wireDropzone($("#docDrop"), (files) => openUploadModal({ onDone: () => ctl.reload() }));
  }
}
