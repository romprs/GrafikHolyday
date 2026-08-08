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
