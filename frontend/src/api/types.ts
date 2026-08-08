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
