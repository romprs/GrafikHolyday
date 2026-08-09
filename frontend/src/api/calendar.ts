import { apiFetch } from "./client";
import type {
  BlockedPeriodOut,
  BlockedRangeOut,
  RestrictionSettingsOut,
  TeamLeaveOut,
} from "./types";

export function getBlockedRanges(dateFrom?: string, dateTo?: string): Promise<BlockedRangeOut[]> {
  const params = new URLSearchParams();
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  const query = params.toString();
  return apiFetch<BlockedRangeOut[]>(`/calendar/blocked${query ? `?${query}` : ""}`);
}

export function getTeamCalendar(): Promise<TeamLeaveOut[]> {
  return apiFetch<TeamLeaveOut[]>("/calendar/team");
}

export function listBlockedPeriods(): Promise<BlockedPeriodOut[]> {
  return apiFetch<BlockedPeriodOut[]>("/blocked-periods");
}

export function createBlockedPeriod(input: {
  date_from: string;
  date_to: string;
  reason: string;
  scope: string;
  org_unit_id?: string | null;
  user_id?: string | null;
}): Promise<BlockedPeriodOut> {
  return apiFetch<BlockedPeriodOut>("/blocked-periods", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function deleteBlockedPeriod(id: string): Promise<void> {
  return apiFetch<void>(`/blocked-periods/${id}`, { method: "DELETE" });
}

export function getRestrictionSettings(): Promise<RestrictionSettingsOut[]> {
  return apiFetch<RestrictionSettingsOut[]>("/restriction-settings");
}
