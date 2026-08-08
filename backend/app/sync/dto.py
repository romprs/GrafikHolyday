from pydantic import BaseModel


class ExternalOrgUnitDTO(BaseModel):
    external_id: str
    parent_external_id: str | None
    name: str
    unit_kind: str | None
    head_external_id: str | None  # external_id пользователя-руководителя


class ExternalUserDTO(BaseModel):
    external_id: str
    email: str
    full_name: str
    org_unit_external_id: str | None
    has_benefits: bool = False
    is_active: bool = True
