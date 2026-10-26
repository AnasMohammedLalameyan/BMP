/* The Secretarial Standards strip above a register's list. The checks themselves are computed on the server. */

import { esc } from "./util.js";

const STYLE = {
  ok: ["#e6f4ea", "#0f7a3d", "#bfe6cd", "✓"],
  attention: ["#fff4e5", "#9a5b00", "#ffd9a0", "!"],
  unknown: ["#eef2f7", "#64748b", "#dbe2ea", "–"],
};

export function complianceStrip(chips, standard) {
  if (!chips || !chips.length) return "";
  const needs = chips.some((c) => c.status === "attention");
  const html = chips.map((c) => {
    const [bg, fg, bd, icon] = STYLE[c.status] || STYLE.unknown;
    return `<span class="ss-chip" style="background:${bg};color:${fg};border-color:${bd}" title="${esc(c.detail)}">`
      + `<b>${icon}</b> ${esc(c.label)} <span class="ss-detail">${esc(c.detail)}</span></span>`;
  }).join("");
  return `<div class="tbl-card p-3 mb-3 no-print" id="complianceCard">
    <div class="d-flex align-items-center gap-2 mb-2"><strong>Secretarial Standards (${esc(standard || "SS-1")})</strong>
      <span class="text-muted small">— from the recorded meetings</span>
      ${needs ? `<span class="badge-soft bs-no">needs attention</span>` : ""}</div>
    <div class="ss-strip">${html}</div></div>`;
}
