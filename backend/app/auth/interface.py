import uuid
from abc import ABC, abstractmethod

from pydantic import BaseModel


class AuthenticatedIdentity(BaseModel):
    """Результат проверки токена/сессии — независим от конкретного провайдера."""

    user_id: uuid.UUID


class AuthProvider(ABC):
    @abstractmethod
    def resolve_identity(self, authorization_header: str | None) -> AuthenticatedIdentity:
        """Проверяет входящие креды запроса и возвращает identity.

        Бросает app.core.exceptions.ForbiddenError при отсутствии/невалидности.
        """
        raise NotImplementedError
