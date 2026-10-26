/* Thin wrappers over api.js for the /minutes endpoints. put() and upload() take no query string, so identifiers
   go in the path or the form. */

import * as api from "./api.js";

export const registers = () => api.get("/minutes/registers");
export const counts = (companyId, fy) => api.get("/minutes/counts", { company_id: companyId, fy });
export const list = (reg, companyId, fy) => api.get(`/minutes/${reg}`, { company_id: companyId, fy });
export const roster = (companyId, date) => api.get("/minutes/roster", { company_id: companyId, date });
export const create = (reg, companyId, body) => api.post(`/minutes/${reg}`, body, { company_id: companyId });
export const update = (reg, companyId, id, body) =>
  api.put(`/minutes/${reg}/${id}?company_id=${encodeURIComponent(companyId)}`, { ...body, company_id: companyId });
export const archive = (id) => api.archiveRecord("meeting", id);
export const exportXlsx = (companyId, fy, reg) =>
  api.download("/minutes/export.xlsx", { company_id: companyId, fy, register: reg }, "Minutes.xlsx");

export function parse(file, companyId) {
  const form = new FormData();
  form.append("company_id", String(companyId));
  form.append("file", file);
  return api.upload("/minutes/parse", form);
}
