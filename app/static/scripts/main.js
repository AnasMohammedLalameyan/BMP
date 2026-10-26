/* Entry point: sign in, load the metadata and the companies, route between views.

   Plain ES modules with no build step (as in the approved dashboard): the browser loads these files as they
   are, so there is nothing to compile and nothing to go stale. */

import * as api from "./api.js";
import { company, entityMeta, state } from "./state.js";
import { $, $$, debounce, esc, toast } from "./util.js";
import { buildSidebar, setActiveLink, updateChips } from "./sidebar.js";
import { renderCompanies } from "./companies.js";
import { renderOverview, updateOverallBadge } from "./overview.js";
import { closeModal, openModal, renderEntityPage } from "./entity.js";
import * as masterdata from "./masterdata.js";
import * as directors from "./directors.js";
import * as shareholders from "./shareholders.js";
import * as foreign from "./foreign.js";
import * as meetings from "./meetings.js";
import * as rules from "./rules.js";
import * as activities from "./activities.js";
import * as documents from "./documents.js";
import * as trail from "./trail.js";
import * as alldirectors from "./alldirectors.js";
import * as notifications from "./notifications.js";
import { activeTabs, clearTabs } from "./tabs.js";

const NAV_KEY = "bmp_nav";
let currentList = null;       // the list on screen, so the header search box can drive it

/* ---------- remembering where the user was (UI position only; never data) ---------- */

function saveNav() {
  try {
    localStorage.setItem(NAV_KEY, JSON.stringify({
      uid: state.user && state.user.id, companyId: state.companyId, fy: state.fy, current: state.current, tab: state.tab,
    }));
  } catch (e) { /* private mode: a refresh just returns to the Companies page */ }
}

function readNav() {
  try {
    const nav = JSON.parse(localStorage.getItem(NAV_KEY) || "null");
    return nav && state.user && nav.uid === state.user.id ? nav : null;
  } catch (e) { return null; }
}

/* ---------- sign in / out ---------- */

function showLogin(message) {
  $("#appShell").classList.add("d-none");
  $("#launcherView").classList.add("d-none");
  $("#loginView").classList.remove("d-none");
  $("#loginError").textContent = message || "";
  $("#loginPassword").value = "";
  setTimeout(() => $("#loginEmail").focus(), 50);
}

function showApp() {
  $("#loginView").classList.add("d-none");
  $("#launcherView").classList.add("d-none");
  $("#appShell").classList.remove("d-none");
}

function showLauncher() {
  $("#loginView").classList.add("d-none");
  $("#appShell").classList.add("d-none");
  $("#launcherWho").textContent = state.user.name;
  $("#launcherView").classList.remove("d-none");
  if (location.hash !== "#/launcher") history.replaceState(null, "", "#/launcher");
}

async function enterDatabase() {
  history.replaceState(null, "", location.pathname + location.search);
  showApp();
  buildSidebar();
  await applyRoute(true);
}

async function startApp(restore = true) {
  state.meta = await api.getMeta();
  state.user = state.meta.user;
  await loadCompanies();
  notifications.refreshBadge();
  $("#whoName").textContent = state.user.name;
  $("#whoSub").textContent = `${state.user.role || "user"} · ${state.user.email}`;
  const h = location.hash;
  if (!h || h === "#/" || h === "#/launcher") { showLauncher(); return; }
  showApp();
  buildSidebar();
  await applyRoute(restore);
}

async function loadCompanies() {
  state.companies = (await api.getCompanies()).companies;
}

async function signOut() {
  try { await api.logout(); } catch (e) { /* the session may already be gone */ }
  notifications.setBadge(0);
  state.user = null; state.csrf = null; state.meta = null; state.overview = null;
  setCompany(null);
  try { localStorage.removeItem(NAV_KEY); } catch (e) { /* ignore */ }
  showLogin();
}

/* ---------- opening a company ---------- */

async function openCompany(id, { fy, view, tab } = {}) {
  setCompany(id);
  state.overview = null;
  state.tab = tab || null;
  const yrs = await api.getYears(id);
  state.currentFy = yrs.current;
  state.years = yrs.years;
  const all = Array.from(new Set([...yrs.years, yrs.current])).sort().reverse();
  state.yearOptions = all;
  state.fy = fy !== undefined && (fy === "" || all.includes(fy)) ? fy : (yrs.years[0] || yrs.current);
  renderFyOptions();
  await loadOverview();
  go(view || "overview");
}

function renderFyOptions() {
  const sel = $("#fySelect");
  sel.innerHTML = `<option value="">All years</option>` + state.yearOptions.map((y) =>
    `<option value="${esc(y)}" ${y === state.fy ? "selected" : ""}>${esc(y)}${y === state.currentFy ? " (current)" : ""}</option>`).join("");
  sel.value = state.fy || "";
}

async function loadOverview() {
  if (state.companyId == null) { state.overview = null; return; }
  try { state.overview = await api.getOverview(state.companyId, state.fy || state.currentFy); }
  catch (e) { state.overview = null; toast(`Could not load the overview: ${e.message}`); }
  updateChips();
  updateOverallBadge();
}

function renderEntityBox() {
  const co = company();
  $("#entityName").textContent = co ? co.name : "—";
  $("#entityMeta").innerHTML = co ? `${esc(co.cin)} &middot; ${esc(co.category || "")}${co.is_listed ? " &middot; Listed" : ""}` : "";
  $("#btnRefresh").disabled = !co;
}

/* ---------- routing ---------- */

const COMPANY_VIEWS = new Set(["overview", "masterdata", "directors", "shareholders", "foreign", "meetings", "rules", "activities", "documents", "trail"]);
const GLOBAL_HASH = { companies: "#/companies", "all-directors": "#/directors", notifications: "#/notifications" };
const HASH_GLOBAL = { companies: "companies", directors: "all-directors", notifications: "notifications" };

/** The company is opened or closed: tell the parts of the page that depend on it (the sidebar). */
function setCompany(id) {
  state.companyId = id;
  if (id == null) { state.overview = null; state.tab = null; updateChips(); updateOverallBadge(); }
  window.dispatchEvent(new CustomEvent("bmp:company-changed", { detail: { companyId: id } }));
}

/* ---------- addresses (#/companies, #/company/{id}/{view}[/{tab}]) ---------- */

function hashFor(view, companyId, tab) {
  if (GLOBAL_HASH[view]) return GLOBAL_HASH[view];
  return `#/company/${companyId}/${view}${tab ? "/" + tab : ""}`;
}

function parseHash(h) {
  const m = /^#\/(.+)$/.exec(h || "");
  if (!m) return null;
  const p = m[1].split("/").map((x) => { try { return decodeURIComponent(x); } catch (e) { return x; } });
  if (p.length === 1 && HASH_GLOBAL[p[0]]) return { view: HASH_GLOBAL[p[0]], companyId: null, tab: null };
  if (p[0] === "company" && /^\d+$/.test(p[1] || "")) return { view: p[2] || "overview", companyId: Number(p[1]), tab: p[3] || null };
  return null;
}

/** A view the app can draw for an open company; anything else (a removed screen, an old bookmark) falls back to the first one. */
function viewKnown(view) {
  return COMPANY_VIEWS.has(view) || (view.startsWith("entity:") && !!entityMeta(view.slice(7)));
}

/** Go to a screen the way a click does: change the address (so Back works) and let the address drive the page. */
export function navigate(view, tab) {
  if (!GLOBAL_HASH[view] && state.companyId == null) { go(view); return; }
  const h = hashFor(view, state.companyId, tab);
  if (location.hash === h) applyRoute(false, true); else location.hash = h;
}

/** Draw whatever the address says. With no usable address, return to the saved position (or the Companies page). */
async function applyRoute(restore = false, force = false) {
  if (!state.user) return;
  if (location.hash === "#/launcher") { showLauncher(); return; }
  let r = parseHash(location.hash);
  if (!r) {
    const nav = restore ? readNav() : null;
    const saved = nav && nav.companyId && state.companies.some((c) => c.id === nav.companyId)
      ? hashFor(nav.current && nav.current !== "companies" ? nav.current : "overview", nav.companyId, nav.tab) : "#/companies";
    history.replaceState(null, "", saved);
    r = parseHash(saved);
  }
  if (r.companyId == null) {
    if (state.companyId != null) setCompany(null);
    state.tab = null;
    go(r.view);
    return;
  }
  if (!state.companies.some((c) => c.id === r.companyId)) { history.replaceState(null, "", "#/companies"); applyRoute(); return; }
  const view = viewKnown(r.view) ? r.view : "overview";
  if (state.companyId !== r.companyId) {
    const nav = readNav();
    await openCompany(r.companyId, { fy: nav && nav.companyId === r.companyId ? nav.fy : undefined, view, tab: view === r.view ? r.tab : null });
    return;
  }
  const tab = view === r.view ? r.tab : null;
  if (view !== r.view) history.replaceState(null, "", hashFor(view, r.companyId));      // a removed / unknown screen: show the address of the one we open
  if (!force && view === state.current) {
    if ((tab || null) === (state.tab || null)) return;            // the address change that follows a tab click: already showing it
    const tabs = activeTabs();
    if (tabs) { tabs.show(tab); return; }                         // Back / Forward between tabs: no redraw
  }
  state.tab = tab;
  go(view);
}

export function go(view) {
  state.current = view;
  render();
  setActiveLink();
  if (window.bootstrap && window.innerWidth < 992) {
    const inst = window.bootstrap.Offcanvas.getInstance($("#sidebar"));
    if (inst) inst.hide();
  }
  try { window.scrollTo(0, 0); } catch (e) { /* not fatal */ }
}

function render() {
  const v = state.current;
  currentList = null;
  clearTabs();
  $("#searchWrap").classList.add("d-none");
  $("#search").value = "";
  const eb = $(".entity-box");
  const noCompany = state.companyId == null;
  eb.classList.toggle("d-none", v === "companies" || noCompany);
  $("#fyWrap").classList.toggle("d-none", noCompany);       // a financial year only means something for a company
  renderEntityBox();

  if (v === "companies") {
    renderCompanies(
      (id) => { location.hash = hashFor("overview", id); },
      async (id) => { await loadCompanies(); location.hash = hashFor("overview", id); });
  } else if (COMPANY_VIEWS.has(v) && noCompany) {
    $("#crumb").textContent = "";
    $("#pageTitle").textContent = "Open a company";
    $("#pageSub").textContent = "";
    $("#view").innerHTML = `<div class="tbl-card p-5 text-center text-muted">Choose a company from <a role="button" data-view="companies">All companies</a> first.</div>`;
  } else if (v === "all-directors") alldirectors.render();
  else if (v === "notifications") notifications.render();
  else if (v === "overview") renderOverview();
  else if (v === "masterdata") masterdata.render(refreshAll);
  else if (v === "directors") directors.render();
  else if (v === "shareholders") shareholders.render();
  else if (v === "foreign") foreign.render();
  else if (v === "meetings") meetings.render();
  else if (v === "rules") rules.render(refreshAll);
  else if (v === "activities") activities.render(refreshAll);
  else if (v === "documents") documents.render();
  else if (v === "trail") trail.render();
  else if (v.startsWith("entity:")) {
    currentList = renderEntityPage(v.slice(7));
    if (currentList) $("#searchWrap").classList.remove("d-none");
  } else renderOverview();

  updateOverallBadge();
  const here = hashFor(v, state.companyId, state.tab);
  if (location.hash !== here) history.replaceState(null, "", here);
  saveNav();
}

/** After a change that other screens' counts depend on: reload the overview and repaint. */
async function refreshAll() {
  await loadOverview();
}

/* ---------- dialogs ---------- */

function passwordDialog() {
  const entry = openModal(`
    <div class="modal-header"><h5 class="modal-title">Change my password</h5><button type="button" class="btn-close" data-close></button></div>
    <div class="modal-body">
      <div class="mb-2"><label class="form-label">Current password</label><input type="password" class="form-control" id="pwCur" autocomplete="current-password"></div>
      <div class="mb-2"><label class="form-label">New password (at least 8 characters)</label><input type="password" class="form-control" id="pwNew" autocomplete="new-password"></div>
      <div class="text-danger small" id="pwErr"></div>
    </div>
    <div class="modal-footer"><button class="btn btn-outline-secondary" data-close>Cancel</button><button class="btn btn-brand" id="pwGo">Change password</button></div>`, { size: "" });
  entry.el.addEventListener("click", async (e) => {
    if (e.target.closest("[data-close]")) { closeModal(entry); return; }
    if (!e.target.closest("#pwGo")) return;
    try {
      await api.post("/auth/password", { current_password: $("#pwCur", entry.el).value, new_password: $("#pwNew", entry.el).value });
      toast("Password changed");
      closeModal(entry);
    } catch (err) { $("#pwErr", entry.el).textContent = err.message; }
  });
}

/* ---------- wiring ---------- */

function wire() {
  // every element carrying data-view navigates (sidebar, overview chips, breadcrumbs, attention items)
  document.addEventListener("click", (e) => {
    const a = e.target.closest("[data-view]");
    if (!a || a.closest("#loginView")) return;
    e.preventDefault();
    navigate(a.dataset.view);
  });
  $("#btnExitCompany").addEventListener("click", () => navigate("companies"));
  window.addEventListener("hashchange", () => applyRoute());
  window.addEventListener("bmp:tab-selected", (e) => {
    const here = hashFor(state.current, state.companyId, e.detail.tab);
    if (location.hash === here) return;
    if (e.detail.user) location.hash = here; else history.replaceState(null, "", here);     // a click makes a history entry; opening a screen does not
  });
  $("#fySelect").addEventListener("change", async (e) => {
    state.fy = e.target.value;
    await loadOverview();
    render();
  });
  $("#search").addEventListener("input", debounce((e) => { if (currentList) currentList.setQuery(e.target.value.trim()); }, 300));
  $("#btnPrint").addEventListener("click", () => window.print());
  $("#btnRefresh").addEventListener("click", async () => {
    const icon = $(".refresh-icon");
    icon.classList.add("spin");
    try { await loadCompanies(); await loadOverview(); render(); notifications.refreshBadge(); toast("Data reloaded"); }
    finally { icon.classList.remove("spin"); }
  });
  $("#btnExportExcel").addEventListener("click", () => {
    if (state.companyId == null) { toast("Open a company first"); return; }
    api.download(`/companies/${state.companyId}/export.xlsx`, {}, "company.xlsx").catch((e) => toast(e.message));
  });
  $("#btnExport").addEventListener("click", () => {
    if (state.companyId == null) { toast("Open a company first"); return; }
    api.download(`/companies/${state.companyId}/export.json`, {}, "company.json").catch((e) => toast(e.message));
  });
  $("#btnChangePassword").addEventListener("click", passwordDialog);
  $("#btnSignOut").addEventListener("click", signOut);

  $("#loginForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = $("#loginBtn");
    btn.disabled = true;
    $("#loginError").textContent = "";
    try {
      const res = await api.login($("#loginEmail").value.trim(), $("#loginPassword").value);
      state.user = res.user;
      state.csrf = res.csrf;
      history.replaceState(null, "", "#/launcher");
      await startApp(true);
    } catch (err) {
      $("#loginError").textContent = err.message;
    } finally { btn.disabled = false; }
  });

  $("#goDatabase").addEventListener("click", enterDatabase);
  $("#goDatabase").addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); enterDatabase(); } });
  $("#launcherSignOut").addEventListener("click", signOut);

  window.addEventListener("bmp:unauthenticated", () => { if (state.user) { state.user = null; showLogin("Your session has ended. Please sign in again."); } });
  // a file dropped outside a drop zone must not make the browser navigate to it
  ["dragover", "drop"].forEach((ev) => window.addEventListener(ev, (e) => e.preventDefault()));
}

(async function boot() {
  wire();
  try {
    const res = await api.me();
    state.user = res.user;
    state.csrf = res.csrf;
    await startApp(true);
  } catch (e) {
    showLogin();
  }
})();
