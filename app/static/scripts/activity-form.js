import { esc, words } from "./util.js";

export function renderStartFields(host, tpl) {
  if (!tpl) { host.innerHTML = ""; return; }
  const props = (tpl.input_schema && tpl.input_schema.properties) || {};
  const req = new Set((tpl.input_schema && tpl.input_schema.required) || []);
  const field = (k, spec) => {
    const label = `${esc(words(k).replace(/^./, (c) => c.toUpperCase()))}${req.has(k) ? ' <span class="req">*</span>' : ""}`;
    let ctl;
    if (k === "venue_mode") ctl = `<select class="form-select form-select-sm" data-p="${k}"><option value="">—</option>${["PHYSICAL", "VC", "HYBRID"].map((o) => `<option>${o}</option>`).join("")}</select>`;
    else if (spec.format === "date") ctl = `<input type="date" class="form-control form-control-sm" data-p="${k}">`;
    else if (spec.type === "array") ctl = `<textarea class="form-control form-control-sm" rows="4" data-p="${k}" data-list="1" placeholder="One per line"></textarea>`;
    else ctl = `<input class="form-control form-control-sm" data-p="${k}" ${k === "start_time" ? 'placeholder="e.g. 11:00"' : ""}>`;
    return `<div class="rec-field ${spec.type === "array" ? "wide" : ""}" data-field="params.${k}"><label>${label}</label>${ctl}
      ${spec.description ? `<div class="help">${esc(spec.description)}</div>` : ""}<div class="err"></div></div>`;
  };
  host.innerHTML = `<div class="rec-grid">${Object.entries(props).map(([k, s]) => field(k, s)).join("")}</div>`;
}

export function collectParams(host) {
  const params = {};
  host.querySelectorAll("[data-p]").forEach((el) => {
    const v = el.value.trim();
    if (!v) return;
    params[el.dataset.p] = el.dataset.list ? v.split("\n").map((x) => x.trim()).filter(Boolean) : v;
  });
  return params;
}

export function clearFieldErrors(host) {
  host.querySelectorAll(".rec-field").forEach((f) => {
    f.classList.remove("has-error");
    const err = f.querySelector(".err");
    if (err) err.textContent = "";
  });
}

export function showFieldErrors(host, err) {
  Object.entries(err.fields || {}).forEach(([k, m]) => {
    const f = host.querySelector(`.rec-field[data-field="${CSS.escape(k)}"]`);
    if (f) {
      f.classList.add("has-error");
      const errEl = f.querySelector(".err");
      if (errEl) errEl.textContent = m;
    }
  });
}
