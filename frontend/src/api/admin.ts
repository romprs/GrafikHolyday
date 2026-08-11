import { apiFetch } from "./client";
import type {
  AuditLogOut,
  LeaveBalanceOut,
  LeaveRequestOut,
  RestrictionSettingsOut,
  SyncRunOut,
  UserWithRoleOut,
} from "./types";

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

export function listUsersWithRoles(): Promise<UserWithRoleOut[]> {
  return apiFetch<UserWithRoleOut[]>("/admin/users");
}

export function grantRole(userId: string, role: string): Promise<void> {
  return apiFetch<void>(`/admin/users/${userId}/roles/${role}`, { method: "POST" });
}

export function revokeRole(userId: string, role: string): Promise<void> {
  return apiFetch<void>(`/admin/users/${userId}/roles/${role}`, { method: "DELETE" });
}

export function getUserBalance(userId: string, year: number): Promise<LeaveBalanceOut> {
  return apiFetch<LeaveBalanceOut>(`/leave-balances/${userId}?year=${year}`);
}

export function setEmployeeCode(userId: string, employeeCode: string | null): Promise<UserWithRoleOut> {
  return apiFetch<UserWithRoleOut>(`/admin/users/${userId}/employee-code`, {
    method: "PATCH",
    body: JSON.stringify({ employee_code: employeeCode }),
  });
}

export function importStudyPeriodsFile(raw: unknown[]): Promise<SyncRunOut> {
  return apiFetch<SyncRunOut>("/admin/study-periods/import", {
    method: "POST",
    body: JSON.stringify(raw),
  });
}

export function triggerStudyPeriodsSync(): Promise<SyncRunOut> {
  return apiFetch<SyncRunOut>("/admin/study-periods/run", { method: "POST" });
}

export function listStudyPeriodsRuns(): Promise<SyncRunOut[]> {
  return apiFetch<SyncRunOut[]>("/admin/study-periods/runs");
}

export function setUserBalance(
  userId: string,
  input: { year: number; accrued_days: number; carried_over_days: number },
): Promise<LeaveBalanceOut> {
  return apiFetch<LeaveBalanceOut>(`/leave-balances/${userId}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}
