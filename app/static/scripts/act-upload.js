/* Upload minutes to auto-fill. The parser only SUGGESTS: it fills the open draft and nothing is saved until the
   person presses Save. Fields that were not found never blank an existing value. */

import * as minApi from "./act-api.js";
import { matchRoster } from "./act-form.js";
import { $, toast, wireDropzone } from "./util.js";

let host = null;
let wired = false;

function modal() {
  return window.bootstrap.Modal.getOrCreateInstance($("#minutesModal"));
}

export function openUploadModal(h) {
  host = h;
  const input = $("#minutesFile");
  if (!wired) {
    wired = true;
    const pick = (files) => {
      const file = files && files[0];
      if (!file) return;
      modal().hide();
      onMinutesUpload(file);
      input.value = "";
    };
    const drop = $("#minutesDrop");
    wireDropzone(drop, pick);
    drop.addEventListener("click", () => input.click());
    drop.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); } });
    input.addEventListener("change", () => pick(input.files));
  }
  modal().show();
}

const set = (draft, key, value) => { if (value) draft[key] = value; };

export async function onMinutesUpload(file) {
  const status = () => $("#minutesStatus");
  if (!host || !host.draft()) return;
  if (status()) status().textContent = "Reading…";
  host.capture();
  let res;
  try {
    res = await minApi.parse(file, host.companyId());
  } catch (e) {
    if (status()) status().textContent = "";
    toast(e.message);
    return;
  }
  const draft = host.draft();
  if (!draft) return;
  const agenda = res.agenda || [];
  if (agenda.length) {                                       // replaced, not merged; none found = untouched
    draft.agenda = agenda.map((a) => ({ id: null, text: a.text, reg30: a.reg30 || "NA",
      forms: (a.forms || []).join(", "), docs: (a.docs || []).join(", "), comments: "" }));
  }
  const p = res.particulars || {};
  if (res.meeting_date) draft.meeting_date = res.meeting_date;
  set(draft, "meeting_time", p.meeting_time);
  set(draft, "chairman", p.chairman);
  set(draft, "invitees_present", p.invitees_present);
  set(draft, "leave_of_absence", p.leave_of_absence);
  set(draft, "notice_date", p.notice_date);
  set(draft, "signing_date", p.signing_date);
  set(draft, "signing_place", p.signing_place);

  if (res.meeting_date) await host.reloadRoster();
  let unmatched = [];
  if (p.directors_present) {
    const m = matchRoster(p.directors_present, host.roster());
    m.matched.forEach((id) => draft.ticked.add(id));
    unmatched = m.unmatched;
    draft._presentTouched = false;                           // Present follows the tick count
  }
  host.redraw();
  const forms = (res.roc_forms || []).length;
  const el = status();
  if (el) {
    el.textContent = `${agenda.length} agenda item(s), ${forms} form(s) detected — review below`
      + (unmatched.length ? `. Not on the board that day, please verify: ${unmatched.join(", ")}` : "");
  }
  toast(`Detected ${agenda.length} agenda items and ${forms} forms from ${res.source || file.name}.`);
}
