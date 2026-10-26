/* Activities Dashboard: boot, sign-in check, company and financial-year pickers, the eight-register sidebar, routing. */

import * as api from "./api.js";
import * as minApi from "./act-api.js";
import * as register from "./act-register.js";
import * as ai from "./act-ai.js";
import { state } from "./state.js";
import { $, $$, esc, toast } from "./util.js";

let registers = [];

function remember(id) {
  try { sessionStorage.setItem("bmp_min_company", String(id)); } catch (e) { /* storage blocked: not remembered */ }
}
function remembered() {
  try { return Number(sessionStorage.getItem("bmp_min_company")) || null; } catch (e) { return null; }
}

async function boot() {
  try {
    const res = await api.me();
    state.user = res.user;
    state.csrf = res.csrf;
  } catch (e) { location.href = "/"; return; }
  try {
    state.companies = (await api.getCompanies()).companies;
    const meta = await minApi.registers();
    registers = meta.registers;
  } catch (e) { toast(e.message); }
  $("#whoName").textContent = state.user.name;
  $("#whoSub").textContent = `${state.user.role || "user"} · ${state.user.email}`;
  $("#btnSignOut").addEventListener("click", async () => {
    try { await api.logout(); } catch (e) { /* already gone */ }
    location.href = "/";
  });
  $("#btnPrint").addEventListener("click", () => window.print());
  window.addEventListener("bmp:unauthenticated", () => { location.href = "/"; });

  await ai.loadStatus();                                      // one call; AI elements stay hidden if it fails or says off
  drawSidebar();
  const co = $("#coSelect");
  co.innerHTML = state.companies.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("");
  const want = remembered();
  state.companyId = state.companies.some((c) => c.id === want) ? want : (state.companies[0] || {}).id || null;
  if (state.companyId != null) co.value = String(state.companyId);
  co.addEventListener("change", async () => {
    state.companyId = Number(co.value);
    remember(state.companyId);
    await loadYears();
    route();
  });
  $("#fySelect").addEventListener("change", () => { state.fy = $("#fySelect").value; route(); });
  $("#btnRefresh").addEventListener("click", () => route());
  window.addEventListener("hashchange", route);
  $("#appShell").classList.remove("d-none");
  if (state.companyId == null) {
    $("#view").innerHTML = `<div class="tbl-card p-5 text-center text-muted">You do not have access to any company yet.</div>`;
    return;
  }
  await loadYears();
  route();
}

function drawSidebar() {
  $("#sideRegisters").innerHTML = registers.map((r) =>
    `<a class="side-link" data-reg="${r.key}" role="button" href="#/${r.key}"><span class="flex-grow-1">${esc(r.name)}</span>
      <span class="cnt" id="cnt-${r.key}" style="display:none"></span></a>`).join("");
}

async function loadYears() {
  let years = [], current = null;
  try {
    const res = await api.getYears(state.companyId);
    years = res.years.slice();
    current = res.current;
  } catch (e) { toast(e.message); }
  if (current && !years.includes(current)) years.unshift(current);
  years.sort().reverse();
  if (!years.length) years = [current || ""];
  state.years = years;
  if (!years.includes(state.fy)) state.fy = current && years.includes(current) ? current : years[0];
  $("#fySelect").innerHTML = years.map((y) => `<option value="${y}">${esc(y)}</option>`).join("");
  $("#fySelect").value = state.fy;
}

async function refreshCounts() {
  try {
    const { counts } = await minApi.counts(state.companyId, state.fy);
    registers.forEach((r) => {
      const el = $(`#cnt-${r.key}`);
      if (!el) return;
      const n = counts[r.key] || 0;
      el.textContent = n;
      el.style.display = n ? "" : "none";
    });
  } catch (e) { /* counts are decoration */ }
}

export async function route() {
  const key = location.hash.replace(/^#\//, "").split("/")[0] || "board";
  const cfg = registers.find((r) => r.key === key) || registers[0];
  if (!cfg) return;
  $$("#sideRegisters .side-link").forEach((a) => a.classList.toggle("active", a.dataset.reg === cfg.key));
  window.scrollTo(0, 0);
  await register.show(cfg, refreshCounts);
  refreshCounts();
}

boot();
