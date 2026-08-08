from pydantic import BaseModel, ConfigDict


class RestrictionSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    enabled: bool
    params: dict
    description: str | None
