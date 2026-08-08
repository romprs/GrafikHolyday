import { apiFetch } from "./client";
import type { OrgLoadOut, SyncRunOut } from "./types";

export function getOrgLoad(orgUnitId: string): Promise<OrgLoadOut> {
  return apiFetch<OrgLoadOut>(`/org-load?org_unit_id=${orgUnitId}`);
}

export function triggerSync(): Promise<SyncRunOut> {
  return apiFetch<SyncRunOut>("/admin/sync/run", { method: "POST" });
}

export function listSyncRuns(): Promise<SyncRunOut[]> {
  return apiFetch<SyncRunOut[]>("/admin/sync/runs");
}
