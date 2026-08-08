from fastapi import APIRouter

from app.dependencies import CurrentUser, DbSession
from app.schemas.user import CurrentUserOut
from app.services import permissions

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=CurrentUserOut)
def get_me(db: DbSession, user: CurrentUser) -> CurrentUserOut:
    role = permissions.resolve_role(db, user)
    return CurrentUserOut(**user.__dict__, role=role)
