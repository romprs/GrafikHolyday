import { apiFetch } from "./client";
import type { LeaveBalanceOut, LeaveRequestOut, LeaveRequestWithEmployeeOut } from "./types";

function qs(params: Record<string, string | number | undefined>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined) as [string, string | number][];
  if (entries.length === 0) return "";
  return "?" + entries.map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join("&");
}

export function listDrafts(year?: number, onBehalfOf?: string): Promise<LeaveRequestOut[]> {
  return apiFetch<LeaveRequestOut[]>(`/leave-requests/drafts${qs({ year, on_behalf_of: onBehalfOf })}`);
}

export function addDraft(input: {
  date_from: string;
  date_to: string;
  comment?: string;
  bonus_requested?: boolean;
  on_behalf_of?: string;
}): Promise<LeaveRequestOut> {
  return apiFetch<LeaveRequestOut>("/leave-requests/drafts", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function removeDraft(id: string): Promise<void> {
  return apiFetch<void>(`/leave-requests/drafts/${id}`, { method: "DELETE" });
}

export function updateDraftBonus(id: string, bonusRequested: boolean): Promise<LeaveRequestOut> {
  return apiFetch<LeaveRequestOut>(`/leave-requests/drafts/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ bonus_requested: bonusRequested }),
  });
}

export function submitDrafts(year?: number, onBehalfOf?: string): Promise<LeaveRequestOut[]> {
  return apiFetch<LeaveRequestOut[]>(`/leave-requests/submit${qs({ year, on_behalf_of: onBehalfOf })}`, {
    method: "POST",
  });
}

export function listMyLeaveRequests(onBehalfOf?: string): Promise<LeaveRequestOut[]> {
  return apiFetch<LeaveRequestOut[]>(`/leave-requests/mine${qs({ on_behalf_of: onBehalfOf })}`);
}

export function cancelLeaveRequest(id: string): Promise<LeaveRequestOut[]> {
  return apiFetch<LeaveRequestOut[]>(`/leave-requests/${id}/cancel`, { method: "POST" });
}

export function managerCancelLeaveRequest(id: string, comment?: string): Promise<LeaveRequestOut[]> {
  return apiFetch<LeaveRequestOut[]>(`/leave-requests/${id}/manager-cancel`, {
    method: "POST",
    body: JSON.stringify({ comment }),
  });
}

export function listPendingForTeam(): Promise<LeaveRequestWithEmployeeOut[]> {
  return apiFetch<LeaveRequestWithEmployeeOut[]>("/leave-requests/team/pending");
}

export function listApprovedForTeam(): Promise<LeaveRequestWithEmployeeOut[]> {
  return apiFetch<LeaveRequestWithEmployeeOut[]>("/leave-requests/team/approved");
}

export function approveLeaveRequest(id: string, comment?: string): Promise<LeaveRequestOut[]> {
  return apiFetch<LeaveRequestOut[]>(`/leave-requests/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({ comment }),
  });
}

export function rejectLeaveRequest(id: string, comment?: string): Promise<LeaveRequestOut[]> {
  return apiFetch<LeaveRequestOut[]>(`/leave-requests/${id}/reject`, {
    method: "POST",
    body: JSON.stringify({ comment }),
  });
}

export function getMyBalance(onBehalfOf?: string): Promise<LeaveBalanceOut> {
  return apiFetch<LeaveBalanceOut>(`/leave-balances/me${qs({ on_behalf_of: onBehalfOf })}`);
}
