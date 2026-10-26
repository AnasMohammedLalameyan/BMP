/* A small tab component used by the screens that group several lists (Master Data, Directors, Shareholders).

   Accessible: a tablist with arrow-key / Home / End navigation and aria-selected. A pane is drawn the first time its tab is opened.
   The open tab is remembered in state.tab and, through the address (#/company/{id}/{view}/{tab}), survives a refresh and the Back button.
   An unknown tab name opens the first tab. The look reuses .rec-tabs / .rec-tab from app.css. */

import { esc } from "./util.js";
import { state } from "./state.js";

let current = null;           // the tab set on screen (main.js asks for it to switch tab on Back / Forward)

/** tabs: [{ id, label, render(paneElement) }]. Returns { show(id) }. */
export function mountTabs(host, tabs, { active } = {}) {
  const first = tabs[0].id;
  host.classList.add("tab-host");
  host.innerHTML = `<div class="rec-tabs" role="tablist">${tabs.map((t) => `<button type="button" class="rec-tab" role="tab"
      id="tab_${esc(t.id)}" data-tab="${esc(t.id)}" aria-controls="pane_${esc(t.id)}" aria-selected="false" tabindex="-1">${esc(t.label)}</button>`).join("")}</div>
    ${tabs.map((t) => `<div class="tab-pane d-none" role="tabpanel" id="pane_${esc(t.id)}" data-pane="${esc(t.id)}" aria-labelledby="tab_${esc(t.id)}"></div>`).join("")}`;
  const list = host.querySelector(".rec-tabs");
  const drawn = new Set();

  function show(id, user = false) {
    if (!tabs.some((t) => t.id === id)) id = first;
    host.querySelectorAll(".rec-tab").forEach((b) => {
      const on = b.dataset.tab === id;
      b.classList.toggle("active", on);
      b.setAttribute("aria-selected", on ? "true" : "false");
      b.tabIndex = on ? 0 : -1;
    });
    host.querySelectorAll(".tab-pane").forEach((p) => p.classList.toggle("d-none", p.dataset.pane !== id));
    state.tab = id;
    if (!drawn.has(id)) {
      drawn.add(id);
      tabs.find((t) => t.id === id).render(host.querySelector(`[data-pane="${CSS.escape(id)}"]`));
    }
    window.dispatchEvent(new CustomEvent("bmp:tab-selected", { detail: { tab: id, user } }));
  }

  list.addEventListener("click", (e) => {
    const b = e.target.closest(".rec-tab");
    if (b) show(b.dataset.tab, true);
  });
  list.addEventListener("keydown", (e) => {
    const keys = { ArrowRight: 1, ArrowLeft: -1, Home: "first", End: "last" };
    if (!(e.key in keys)) return;
    e.preventDefault();
    const ids = tabs.map((t) => t.id);
    const at = ids.indexOf(state.tab);
    const next = keys[e.key] === "first" ? 0 : keys[e.key] === "last" ? ids.length - 1 : (at + keys[e.key] + ids.length) % ids.length;
    show(ids[next], true);
    host.querySelector(`.rec-tab[data-tab="${CSS.escape(ids[next])}"]`).focus();
  });

  current = { show: (id) => show(id, false) };
  show(active);
  return current;
}

export const activeTabs = () => current;
export function clearTabs() { current = null; }
