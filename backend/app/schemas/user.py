import uuid

from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    org_unit_id: uuid.UUID | None
    has_benefits: bool
    is_active: bool


class CurrentUserOut(UserOut):
    role: str  # "employee" | "manager" | "hr_admin"
    # role — это ПРИОРИТЕТ (hr_admin перекрывает manager, см.
    # permissions.resolve_role), а не полный список возможностей: HR-admin,
    # который одновременно возглавляет подразделение, иначе не увидел бы у
    # себя пункт "Согласование" для собственных подчинённых. Отдельный флаг,
    # не зависящий от role, чтобы фронтенд мог показать пункт меню и такому
    # пользователю тоже.
    is_org_unit_head: bool
    # Право согласовывать заявки СВОЕГО подразделения независимо от роли —
    # для заместителя руководителя (см. app/models/user.py, is_approver).
    is_approver: bool
