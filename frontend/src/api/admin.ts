import { apiFetch } from "./client";
import type { AuditLogOut, LeaveRequestOut, RestrictionSettingsOut } from "./types";

export function updateRestrictionSetting(
  key: string,
  input: { enabled: boolean; params: Record<string, unknown> },
): Promise<RestrictionSettingsOut> {
  return apiFetch<RestrictionSettingsOut>(`/restriction-settings/${key}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export function listAllLeaveRequests(): Promise<LeaveRequestOut[]> {
  return apiFetch<LeaveRequestOut[]>("/leave-requests/all");
}

export function adminOverrideLeaveRequest(
  id: string,
  input: { reason: string; date_from?: string; date_to?: string; status?: string },
): Promise<LeaveRequestOut> {
  return apiFetch<LeaveRequestOut>(`/leave-requests/${id}/admin-override`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function listAuditLog(): Promise<AuditLogOut[]> {
  return apiFetch<AuditLogOut[]>("/admin/audit-log");
}
