import { apiFetch } from "./client";
import type {
  AuditLogOut,
  LeaveBalanceOut,
  LeaveRequestOut,
  OrgUnitOut,
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

export function triggerVacationDaysSync(): Promise<SyncRunOut> {
  return apiFetch<SyncRunOut>("/admin/vacation-days/run", { method: "POST" });
}

export function listVacationDaysRuns(): Promise<SyncRunOut[]> {
  return apiFetch<SyncRunOut[]>("/admin/vacation-days/runs");
}

export function createOrgUnit(input: {
  name: string;
  unit_kind?: string | null;
  parent_id?: string | null;
  head_user_id?: string | null;
}): Promise<OrgUnitOut> {
  return apiFetch<OrgUnitOut>("/org-units", { method: "POST", body: JSON.stringify(input) });
}

export function updateOrgUnit(
  id: string,
  input: {
    name: string;
    unit_kind?: string | null;
    parent_id?: string | null;
    head_user_id?: string | null;
    is_active: boolean;
  },
): Promise<OrgUnitOut> {
  return apiFetch<OrgUnitOut>(`/org-units/${id}`, { method: "PATCH", body: JSON.stringify(input) });
}

export function deleteOrgUnit(id: string): Promise<OrgUnitOut> {
  return apiFetch<OrgUnitOut>(`/org-units/${id}`, { method: "DELETE" });
}

export function createUser(input: {
  email: string;
  full_name: string;
  org_unit_id?: string | null;
  has_benefits?: boolean;
  employee_code?: string | null;
}): Promise<UserWithRoleOut> {
  return apiFetch<UserWithRoleOut>("/admin/users", { method: "POST", body: JSON.stringify(input) });
}

export function updateUser(
  id: string,
  input: {
    email: string;
    full_name: string;
    org_unit_id?: string | null;
    has_benefits: boolean;
    is_active: boolean;
  },
): Promise<UserWithRoleOut> {
  return apiFetch<UserWithRoleOut>(`/admin/users/${id}`, { method: "PATCH", body: JSON.stringify(input) });
}

export function deleteUser(id: string): Promise<UserWithRoleOut> {
  return apiFetch<UserWithRoleOut>(`/admin/users/${id}`, { method: "DELETE" });
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
