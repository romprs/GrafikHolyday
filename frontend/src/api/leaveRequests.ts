import { apiFetch } from "./client";
import type { LeaveBalanceOut, LeaveRequestOut } from "./types";

export function listDrafts(year?: number): Promise<LeaveRequestOut[]> {
  return apiFetch<LeaveRequestOut[]>(`/leave-requests/drafts${year ? `?year=${year}` : ""}`);
}

export function addDraft(input: {
  date_from: string;
  date_to: string;
  comment?: string;
}): Promise<LeaveRequestOut> {
  return apiFetch<LeaveRequestOut>("/leave-requests/drafts", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function removeDraft(id: string): Promise<void> {
  return apiFetch<void>(`/leave-requests/drafts/${id}`, { method: "DELETE" });
}

export function submitDrafts(year?: number): Promise<LeaveRequestOut[]> {
  return apiFetch<LeaveRequestOut[]>(`/leave-requests/submit${year ? `?year=${year}` : ""}`, {
    method: "POST",
  });
}

export function listMyLeaveRequests(): Promise<LeaveRequestOut[]> {
  return apiFetch<LeaveRequestOut[]>("/leave-requests/mine");
}

export function cancelLeaveRequest(id: string): Promise<LeaveRequestOut> {
  return apiFetch<LeaveRequestOut>(`/leave-requests/${id}/cancel`, { method: "POST" });
}

export function listPendingForTeam(): Promise<LeaveRequestOut[]> {
  return apiFetch<LeaveRequestOut[]>("/leave-requests/team/pending");
}

export function approveLeaveRequest(id: string, comment?: string): Promise<LeaveRequestOut> {
  return apiFetch<LeaveRequestOut>(`/leave-requests/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({ comment }),
  });
}

export function rejectLeaveRequest(id: string, comment?: string): Promise<LeaveRequestOut> {
  return apiFetch<LeaveRequestOut>(`/leave-requests/${id}/reject`, {
    method: "POST",
    body: JSON.stringify({ comment }),
  });
}

export function getMyBalance(): Promise<LeaveBalanceOut> {
  return apiFetch<LeaveBalanceOut>("/leave-balances/me");
}
