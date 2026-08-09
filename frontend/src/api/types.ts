export interface UserOut {
  id: string;
  email: string;
  full_name: string;
  org_unit_id: string | null;
  has_benefits: boolean;
  is_active: boolean;
}

export interface CurrentUserOut extends UserOut {
  role: "employee" | "manager" | "hr_admin";
}

export interface OrgUnitOut {
  id: string;
  parent_id: string | null;
  name: string;
  unit_kind: string | null;
  head_user_id: string | null;
  is_active: boolean;
}

export type LeaveRequestStatus =
  | "draft"
  | "pending_approval"
  | "approved"
  | "rejected"
  | "cancelled";

export interface LeaveRequestOut {
  id: string;
  user_id: string;
  date_from: string;
  date_to: string;
  comment: string | null;
  status: LeaveRequestStatus;
  bonus_requested: boolean;
  submission_id: string | null;
  reviewer_id: string | null;
  review_comment: string | null;
  submitted_at: string | null;
  reviewed_at: string | null;
  cancelled_at: string | null;
  days: number;
}

export interface LeaveRequestWithEmployeeOut extends LeaveRequestOut {
  user_full_name: string;
}

export interface LeaveBalanceOut {
  year: number;
  accrued_days: number;
  carried_over_days: number;
  used_days: number;
  remaining_days: number;
}

export type BlockedPeriodScope = "global" | "org_unit" | "user";

export interface BlockedPeriodOut {
  id: string;
  date_from: string;
  date_to: string;
  reason: string;
  scope: BlockedPeriodScope;
  org_unit_id: string | null;
  user_id: string | null;
  is_active: boolean;
  created_by: string;
}

export interface BlockedRangeOut {
  date_from: string;
  date_to: string;
  reason: string;
}

export interface TeamLeaveOut {
  user_id: string;
  date_from: string;
  date_to: string;
  status: LeaveRequestStatus;
}

export interface RestrictionSettingsOut {
  key: string;
  enabled: boolean;
  params: Record<string, unknown>;
  description: string | null;
}

export type LoadBand = "green" | "yellow" | "red";

export interface OrgLoadDayOut {
  date: string;
  on_leave: number;
  headcount: number;
  fraction: number;
  band: LoadBand;
}

export interface OrgLoadOut {
  org_unit_id: string;
  headcount: number;
  days: OrgLoadDayOut[];
}

export type EmployeeRole = "employee" | "manager" | "hr_admin";

export interface OrgLoadEmployeeOut {
  id: string;
  full_name: string;
  role: EmployeeRole;
}

export interface OrgLoadLeaveEntryOut {
  id: string;
  user_id: string;
  date_from: string;
  date_to: string;
  status: LeaveRequestStatus;
  submission_id: string | null;
}

export interface OrgLoadDetailOut {
  org_unit_id: string;
  employees: OrgLoadEmployeeOut[];
  leaves: OrgLoadLeaveEntryOut[];
}

export type SyncRunStatus = "running" | "success" | "failed" | "partial";

export interface SyncRunOut {
  id: string;
  started_at: string;
  finished_at: string | null;
  trigger_type: "scheduled" | "manual";
  triggered_by: string | null;
  status: SyncRunStatus;
  summary: {
    org_units?: { created: number; updated: number; unchanged: number };
    users?: { created: number; updated: number; unchanged: number };
  };
  error_message: string | null;
}

export interface AuditLogOut {
  id: string;
  entity_type: string;
  entity_id: string;
  action: string;
  performed_by: string;
  reason: string;
  before_state: Record<string, unknown>;
  after_state: Record<string, unknown>;
  created_at: string;
}

export interface UserWithRoleOut {
  id: string;
  email: string;
  full_name: string;
  org_unit_id: string | null;
  has_benefits: boolean;
  is_active: boolean;
  role: "employee" | "manager" | "hr_admin";
}
