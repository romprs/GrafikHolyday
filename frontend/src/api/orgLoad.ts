import { apiFetch } from "./client";
import type { OrgLoadDetailOut, OrgLoadOut, SyncRunOut } from "./types";

export function getOrgLoad(orgUnitId: string): Promise<OrgLoadOut> {
  return apiFetch<OrgLoadOut>(`/org-load?org_unit_id=${orgUnitId}`);
}

export function getOrgLoadDetail(orgUnitId: string): Promise<OrgLoadDetailOut> {
  return apiFetch<OrgLoadDetailOut>(`/org-load/detail?org_unit_id=${orgUnitId}`);
}

export function triggerSync(): Promise<SyncRunOut> {
  return apiFetch<SyncRunOut>("/admin/sync/run", { method: "POST" });
}

export function listSyncRuns(): Promise<SyncRunOut[]> {
  return apiFetch<SyncRunOut[]>("/admin/sync/runs");
}

export function importOrgDirectoryFile(input: {
  departments?: string;
  employees?: string;
}): Promise<SyncRunOut> {
  return apiFetch<SyncRunOut>("/admin/sync/import", {
    method: "POST",
    body: JSON.stringify(input),
  });
}
