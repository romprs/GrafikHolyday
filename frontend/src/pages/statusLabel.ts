import type { LeaveRequestStatus } from "../api/types";

const labels: Record<LeaveRequestStatus, string> = {
  draft: "Черновик",
  pending_approval: "На согласовании",
  approved: "Согласована",
  rejected: "Отклонена",
  cancelled: "Отменена",
};

export function statusLabel(status: LeaveRequestStatus): string {
  return labels[status] ?? status;
}

const badgeClasses: Record<LeaveRequestStatus, string> = {
  draft: "neutral",
  pending_approval: "wait",
  approved: "ok",
  rejected: "bad",
  cancelled: "neutral",
};

export function statusBadgeClass(status: LeaveRequestStatus): string {
  return badgeClasses[status] ?? "neutral";
}
