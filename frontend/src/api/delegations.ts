import { apiFetch } from "./client";
import type { DelegationTargetOut, LeaveDelegationOut } from "./types";

export function listDelegations(): Promise<LeaveDelegationOut[]> {
  return apiFetch<LeaveDelegationOut[]>("/delegations");
}

export function createDelegation(input: {
  delegate_user_id: string;
  target_user_id?: string;
  target_org_unit_id?: string;
}): Promise<LeaveDelegationOut> {
  return apiFetch<LeaveDelegationOut>("/delegations", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function revokeDelegation(id: string): Promise<void> {
  return apiFetch<void>(`/delegations/${id}`, { method: "DELETE" });
}

export function listMyDelegationTargets(): Promise<DelegationTargetOut[]> {
  return apiFetch<DelegationTargetOut[]>("/delegations/my-targets");
}

export function listDelegationDirectory(): Promise<DelegationTargetOut[]> {
  return apiFetch<DelegationTargetOut[]>("/delegations/directory");
}
