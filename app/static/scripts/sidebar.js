/* The accordion of groups down the left (same markup and classes as the approved dashboard).
   Built from the navigation the server sends, so a user only sees the screens they may open. */

import { $, $$, esc } from "./util.js";
import { state } from "./state.js";

const ICON = (d) => `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">${d}</svg>`;
export const GROUP_ICONS = {
  ca: ICON('<path d="M4 21h16M6 21V9l6-4 6 4v12M10 21v-6h4v6"/>'),
  building: ICON('<path d="M4 21V5l8-3 8 3v16M9 21v-5h6v5M8 8h2M14 8h2M8 12h2M14 12h2"/>'),
  people: ICON('<circle cx="9" cy="8" r="3.2"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6M16 11a3 3 0 1 0 0-6M17 14c2.6.4 4.5 2.6 4.5 5.5"/>'),
  capital: ICON('<path d="M3 20h18M6 20V10M11 20V4M16 20v-7M21 20V8"/>'),
  gov: ICON('<path d="M4 9h16M7 3v3M17 3v3"/><path d="M4 6h16v14a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1z"/><path d="M8 14h3M8 17h6"/>'),
  fin: ICON('<path d="M4 4h16v5H4zM4 13h16v7H4zM8 6.5h.01M8 16h7"/>'),
  docs: ICON('<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/>'),
  admin: ICON('<path d="M12 2l7 4v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z"/><path d="M9 12l2 2 4-4"/>'),
};

/* With no company open the sidebar offers exactly these three links and nothing else. */
const GLOBAL_LINKS = [
  { view: "companies", label: "All Companies", icon: ICON('<path d="M3 21V7l6-4 6 4v14"/><path d="M15 21V11l6-4v14"/><path d="M3 21h18"/>') },
  { view: "all-directors", label: "All Directors", icon: GROUP_ICONS.people },
  { view: "notifications", label: "Notifications", icon: ICON('<path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/>') },
];

function globalLinkHTML(l) {
  return `<a class="side-top" data-view="${esc(l.view)}" role="button">${l.icon}<span class="flex-grow-1">${esc(l.label)}</span></a>`;
}

function accItem(id, icon, title, body, open) {
  return `<div class="accordion-item">
    <h2 class="accordion-header">
      <button class="accordion-button ${open ? "" : "collapsed"}" type="button" data-bs-toggle="collapse"
        data-bs-target="#acc_${esc(id)}" aria-expanded="${open ? "true" : "false"}" aria-controls="acc_${esc(id)}">
        <span class="acc-ic">${icon}</span>${esc(title)}
      </button>
    </h2>
    <div id="acc_${esc(id)}" class="accordion-collapse collapse ${open ? "show" : ""}" data-bs-parent="#sideAcc">
      <div class="accordion-body">${body}</div>
    </div>
  </div>`;
}

function linkHTML(item) {
  const view = item.entity ? `entity:${item.entity}` : item.view;
  return `<a class="side-link" data-view="${esc(view)}" role="button"><span>${esc(item.label)}</span>
    <span class="cnt" data-chip="${esc(view)}" style="display:none"></span></a>`;
}

export function buildSidebar() {
  const global = state.companyId == null;
  $("#sidebar").classList.toggle("sidebar-global-only", global);
  $("#navCompanies").classList.toggle("d-none", global);        // in the global state it is the first of the three links
  $("#sideGlobal").innerHTML = global && state.meta ? GLOBAL_LINKS.map(globalLinkHTML).join("") : "";
  if (global || !state.meta) { $("#sideAcc").innerHTML = ""; setActiveLink(); return; }
  $("#sideAcc").innerHTML = state.meta.nav.map((g) => accItem(
    g.id, GROUP_ICONS[g.icon] || GROUP_ICONS.fin, g.title, g.items.map(linkHTML).join(""), !!g.open)).join("");
  setActiveLink();
  updateChips();
}

// the sidebar follows the open company: main.js announces every open and close
window.addEventListener("bmp:company-changed", () => buildSidebar());

export function setActiveLink() {
  $$("#sideAcc .side-link, .side-top").forEach((a) => {
    a.classList.toggle("active", a.dataset.view === state.current);
  });
  // open the group that holds the active link so the user always sees where they are
  const active = $("#sideAcc .side-link.active");
  if (active) {
    const panel = active.closest(".accordion-collapse");
    if (panel && !panel.classList.contains("show") && window.bootstrap) {
      window.bootstrap.Collapse.getOrCreateInstance(panel, { toggle: false }).show();
    }
  }
}

function chip(view, text, cls) {
  const el = $(`[data-chip="${CSS.escape(view)}"]`);
  if (!el) return;
  if (!text) { el.style.display = "none"; return; }
  el.style.display = "";
  el.textContent = text;
  el.className = "cnt" + (cls ? " " + cls : "");
}

/** Count chips come from the overview, so they cost no extra requests. */
export function updateChips() {
  const o = state.overview;
  $$("[data-chip]").forEach((el) => { el.style.display = "none"; });
  if (!o) return;
  chip("directors", o.tiles.directors, "");
  chip("entity:government_filing", o.tiles.overdue_filings, "cnt-warn");
  chip("activities", o.tiles.open_tasks, o.tiles.overdue_tasks ? "cnt-warn" : "");
  chip("rules", o.rules.action_required, "cnt-warn");
}
