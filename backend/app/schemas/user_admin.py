import uuid
from datetime import date

from pydantic import BaseModel


class UserWithRoleOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    org_unit_id: uuid.UUID | None
    has_benefits: bool
    is_active: bool
    role: str
    employee_code: str | None = None
    # Синкаются из источника дней отпуска (app/integrations/vacation_days.py) —
    # используются для ограничения на выплату ЕСВ по стажу, но HR полезно
    # видеть их и просто как факт (когда принят/уволен), не только через это
    # ограничение — см. RestrictionSettingsPage.
    hire_date: date | None = None
    termination_date: date | None = None
    # Право согласовывать заявки своего подразделения независимо от того,
    # является ли сотрудник head_user_id юнита — для заместителя
    # руководителя (см. app/models/user.py, approval_service.approval_unit_ids).
    is_approver: bool = False


class EmployeeCodeIn(BaseModel):
    employee_code: str | None = None


class UserCreate(BaseModel):
    email: str
    full_name: str
    org_unit_id: uuid.UUID | None = None
    has_benefits: bool = False
    employee_code: str | None = None


class UserUpdate(BaseModel):
    email: str
    full_name: str
    org_unit_id: uuid.UUID | None = None
    has_benefits: bool = False
    is_active: bool = True
    # Обычно приходят синком (см. UserWithRoleOut.hire_date) — эти поля
    # позволяют HR поправить их вручную, пока синк не настроен или ошибся.
    hire_date: date | None = None
    termination_date: date | None = None
    is_approver: bool = False
