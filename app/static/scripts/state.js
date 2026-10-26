/* The one shared object every view reads. Server data lives on the server; this holds only what the page
   needs to know right now: who is signed in, the metadata, and which company / year / view is open. */

export const state = {
  user: null,          // {id, email, name, role, is_admin, is_staff, access}
  csrf: null,
  meta: null,          // {entities, views, nav, lookups, policy}
  companies: [],
  companyId: null,
  fy: null,            // a financial year like "2024-25", or "" for all years
  years: [],
  currentFy: null,
  current: "companies",   // which view is open: "overview", "masterdata", "entity:<key>", ...
  tab: null,           // the open tab inside a tabbed screen (Master Data, Directors, Shareholders), or null
  overview: null,      // cached overview of the open company (counts for the sidebar chips)
};

export const company = () => state.companies.find((c) => c.id === state.companyId) || null;

export const entityMeta = (key) => (state.meta && state.meta.entities[key]) || null;

export const colMeta = (key, name) => {
  const e = entityMeta(key);
  return e ? e.columns.find((c) => c.name === name) : null;
};

/** Can the signed-in user change records of this company (write or admin level)? */
export const canWriteCompany = () => {
  if (!state.user || state.companyId == null) return false;
  const level = state.user.access[String(state.companyId)];
  return level === "write" || level === "admin";
};

/** Whether the "+ Add" / edit controls should be offered for this kind of record. The server remains the
    authority; this only avoids showing buttons that would be refused. */
export const canWriteEntity = (key) => {
  const e = entityMeta(key);
  if (!e || !e.can_write) return false;
  if (e.write_mode === "company") return canWriteCompany();
  return true;
};

/** Lookup list entries ({id, code, label}) for a Standard List code. */
export const lookup = (code) => (state.meta && state.meta.lookups[code]) || [];

export const lookupLabel = (code, id) => {
  const hit = lookup(code).find((x) => x.id === id);
  return hit ? hit.label : null;
};
