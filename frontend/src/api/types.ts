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
  reviewer_id: string | null;
  review_comment: string | null;
  submitted_at: string | null;
  reviewed_at: string | null;
  cancelled_at: string | null;
  days: number;
}

export interface LeaveBalanceOut {
  year: number;
  accrued_days: number;
  carried_over_days: number;
  used_days: number;
  remaining_days: number;
}
