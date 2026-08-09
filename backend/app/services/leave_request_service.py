import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationFailedError
from app.models.leave_request import (
    APPROVED,
    CANCELLED,
    DRAFT,
    PENDING_APPROVAL,
    LeaveRequest,
)
from app.models.leave_type import LeaveType
from app.models.restriction_settings import VACATION_BONUS
from app.models.user import User
from app.services import leave_balance_service, restriction_settings_service
from app.services.validation import engine as validation_engine


def _get_vacation_leave_type(db: Session) -> LeaveType:
    leave_type = db.scalar(select(LeaveType).where(LeaveType.code == "vacation"))
    if leave_type is None:
        raise NotFoundError("Тип отсутствия 'vacation' не настроен")
    return leave_type


def _validate_bonus_request(db: Session, date_from: date, date_to: date, bonus_requested: bool) -> None:
    if not bonus_requested:
        return
    setting = restriction_settings_service.get(db, VACATION_BONUS)
    if setting is None or not setting.enabled:
        raise ValidationFailedError("Программа дополнительной выплаты к отпуску сейчас отключена")
    min_days = setting.params.get("min_days", 14)
    days = (date_to - date_from).days + 1
    if days <= min_days:
        raise ValidationFailedError(
            f"Дополнительную выплату можно запросить только к отпуску длительностью более "
            f"{min_days} дн. (выбрано {days} дн.)",
            {"selected_days": days, "min_days": min_days},
        )


def create_draft(
    db: Session,
    user: User,
    date_from: date,
    date_to: date,
    comment: str | None,
    bonus_requested: bool = False,
) -> LeaveRequest:
    """Добавляет период в текущий план отпуска (черновик — переживает
    переключение вкладок/перезагрузку страницы, в отличие от состояния формы).

    Проходит те же правила, что и обычная заявка (мин. длительность,
    блокировки, остаток баланса с учётом уже добавленных черновиков,
    пересечение с другими своими периодами, включая черновики) — поэтому
    нельзя добавить период, который в сумме с уже добавленными превысит
    остаток: get_remaining_for_new_request и own_overlap_rule учитывают
    статус draft наравне с pending/approved (см. модель LeaveRequest.STATUSES
    и services/validation/*_rule.py).
    """
    violations = validation_engine.validate_leave_request(db, user, date_from, date_to)
    if violations:
        first = violations[0]
        raise ValidationFailedError(
            first.message_ru,
            {"violations": [v.__dict__ for v in violations]},
        )
    _validate_bonus_request(db, date_from, date_to, bonus_requested)

    leave_type = _get_vacation_leave_type(db)
    request = LeaveRequest(
        user_id=user.id,
        leave_type_id=leave_type.id,
        date_from=date_from,
        date_to=date_to,
        comment=comment,
        status=DRAFT,
        bonus_requested=bonus_requested,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def list_drafts(db: Session, user: User, year: int) -> list[LeaveRequest]:
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    return list(
        db.scalars(
            select(LeaveRequest)
            .where(
                LeaveRequest.user_id == user.id,
                LeaveRequest.status == DRAFT,
                LeaveRequest.date_from <= year_end,
                LeaveRequest.date_to >= year_start,
            )
            .order_by(LeaveRequest.date_from)
        ).all()
    )


def delete_draft(db: Session, user: User, request_id: uuid.UUID) -> None:
    request = get_own(db, user, request_id)
    if request.status != DRAFT:
        raise ForbiddenError(
            "Убрать можно только ещё не отправленный период", {"current_status": request.status}
        )
    db.delete(request)
    db.commit()


def submit_drafts(db: Session, user: User, year: int) -> list[LeaveRequest]:
    """Отправляет на согласование весь текущий план на год разом.

    Заявка обязана полностью выбирать доступный остаток — частичная отправка
    запрещена, это и есть контроль "один человек — одна заявка в год": после
    полной отправки остаток становится равен 0, и добавить (тем более
    отправить) что-то ещё в этом году уже нельзя, пока часть периодов не
    отменят/отклонят и остаток не освободится.
    """
    drafts = list_drafts(db, user, year)
    if not drafts:
        raise ValidationFailedError("Нет добавленных периодов для отправки")

    draft_ids = {d.id for d in drafts}
    total_days = sum((d.date_to - d.date_from).days + 1 for d in drafts)

    if not user.has_benefits:
        available = leave_balance_service.get_remaining_for_new_request(
            db, user, year, exclude_request_ids=draft_ids
        )
        if total_days != available:
            raise ValidationFailedError(
                f"Заявка должна использовать весь доступный остаток: выбрано {total_days} дн., "
                f"доступно {available} дн. Добавьте ещё периоды или уберите лишние.",
                {"selected_days": total_days, "available_days": available},
            )

    now = datetime.now(timezone.utc)
    for draft in drafts:
        draft.status = PENDING_APPROVAL
        draft.submitted_at = now
    db.commit()
    for draft in drafts:
        db.refresh(draft)
    return drafts


def get_own(db: Session, user: User, request_id: uuid.UUID) -> LeaveRequest:
    request = db.get(LeaveRequest, request_id)
    if request is None or request.user_id != user.id:
        raise NotFoundError("Заявка не найдена")
    return request


def list_team_leave(db: Session, user: User, date_from: date, date_to: date) -> list[LeaveRequest]:
    """Отпуска коллег по прямому отделу — и согласованные, и на согласовании
    (черновики и отклонённые/отменённые не показываем — это не реальные
    претенденты на пересечение). Руководителю нужно видеть pending, чтобы
    оценить пересечения перед решением об согласовании."""
    if user.org_unit_id is None:
        return []
    return list(
        db.scalars(
            select(LeaveRequest)
            .join(User, User.id == LeaveRequest.user_id)
            .where(
                User.org_unit_id == user.org_unit_id,
                LeaveRequest.status.in_((APPROVED, PENDING_APPROVAL)),
                LeaveRequest.date_from <= date_to,
                LeaveRequest.date_to >= date_from,
            )
            .order_by(LeaveRequest.date_from)
        ).all()
    )


def list_own(db: Session, user: User) -> list[LeaveRequest]:
    return list(
        db.scalars(
            select(LeaveRequest)
            .where(LeaveRequest.user_id == user.id, LeaveRequest.status != DRAFT)
            .order_by(LeaveRequest.date_from.desc())
        ).all()
    )


def cancel(db: Session, user: User, request_id: uuid.UUID) -> LeaveRequest:
    request = get_own(db, user, request_id)
    if request.status not in (PENDING_APPROVAL, APPROVED):
        raise ForbiddenError(
            "Отменить можно только заявку в статусе 'на согласовании' или 'согласована'",
            {"current_status": request.status},
        )

    request.status = CANCELLED
    request.cancelled_at = datetime.now(timezone.utc)
    request.cancelled_by = user.id
    db.commit()
    db.refresh(request)
    return request
