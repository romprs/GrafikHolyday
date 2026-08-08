from fastapi import Request, status
from fastapi.responses import JSONResponse


class DomainError(Exception):
    """Базовая ошибка домена. Отдаётся клиенту как {code, message_ru, params}."""

    http_status = status.HTTP_400_BAD_REQUEST
    code = "DOMAIN_ERROR"

    def __init__(self, message_ru: str, params: dict | None = None):
        self.message_ru = message_ru
        self.params = params or {}
        super().__init__(message_ru)


class NotFoundError(DomainError):
    http_status = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"


class ForbiddenError(DomainError):
    http_status = status.HTTP_403_FORBIDDEN
    code = "FORBIDDEN"


class ValidationFailedError(DomainError):
    """Нарушено одно или несколько бизнес-правил (валидатор заявки и т.п.)."""

    http_status = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "VALIDATION_FAILED"


class ConflictError(DomainError):
    """Недопустимый переход состояния (например, approve уже согласованной заявки)."""

    http_status = status.HTTP_409_CONFLICT
    code = "CONFLICT"


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "code": exc.code,
            "message_ru": exc.message_ru,
            "params": exc.params,
        },
    )


def register_exception_handlers(app) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)
