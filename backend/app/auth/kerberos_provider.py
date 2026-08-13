"""Kerberos/SPNEGO — вход через AD-домен corp.amurgpz.ru, логин = локальная
часть Kerberos-принципала, сопоставляется с локальной частью User.email
(она же — логин, которым синк оргструктуры заполняет email, см.
app/integrations/org_directory.py).

Два режима, переключаются settings.kerberos_mode — от этого зависит, какой
уровень проверяет сам SPNEGO-тикет и где лежит keytab:

- "nginx"  — тикет проверяет nginx (модуль mod_auth_gssapi), бэкенду
  передаётся уже подтверждённый логин в заголовке
  settings.kerberos_trusted_header. Бэкенд Kerberos вообще не касается —
  ни keytab, ни python-gssapi ему не нужны. Безопасно только если бэкенд
  физически недостижим иначе, кроме как через nginx (см. deploy/redos8:
  uvicorn слушает 127.0.0.1, наружу торчит только nginx).
- "python" — тикет проверяет сам бэкенд через python-gssapi и
  settings.kerberos_keytab_path; nginx в этом случае — обычный прозрачный
  прокси, ничего не знающий про Kerberos. Требует установленный пакет
  python-gssapi и системную библиотеку Kerberos на сервере (см.
  deploy/redos8/README.md — в офлайн-бандле это отдельный шаг сборки,
  готовых бинарных колёс под это на PyPI нет).
"""

import base64
import binascii
import logging
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import AuthChallengeError, ForbiddenError
from app.models.user import User

logger = logging.getLogger(__name__)

NEGOTIATE = "Negotiate"


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def resolve_login(db: Session, login: str) -> User:
    """login — локальная часть Kerberos-принципала/email, без домена/реалма."""
    login = login.strip().lower()
    if not login:
        raise ForbiddenError("Пустой логин после проверки Kerberos-тикета")
    user = db.scalar(
        select(User).where(
            User.email.ilike(_escape_like(login) + "@%", escape="\\"),
            User.is_active,
        )
    )
    if user is None:
        raise ForbiddenError(f"Пользователь с логином «{login}» не найден или деактивирован")
    return user


def principal_to_login(principal: str) -> str:
    """"ivanov@CORP.AMURGPZ.RU" -> "ivanov". На случай принципала с
    инстансом ("ivanov/admin@REALM") берём часть до "/" — этот случай в
    обычном пользовательском входе не встречается, но на всякий случай."""
    local = principal.split("@", 1)[0]
    return local.split("/", 1)[0]


def login_from_trusted_header(raw_value: str) -> str:
    """Значение settings.kerberos_trusted_header, которое проставляет
    nginx (mod_auth_gssapi) после успешной проверки тикета. Модуль обычно
    кладёт туда полный принципал ("ivanov@CORP.AMURGPZ.RU"), но на случай
    иной настройки (просто логин без реалма) principal_to_login отработает
    так же корректно — split на "@"/"/", которых там просто не будет."""
    return principal_to_login(raw_value)


class KerberosGSSAPIAuthProvider:
    """Режим "python": SPNEGO-негоциация прямо в бэкенде. gssapi
    импортируется лениво в конструкторе — чтобы пакет был обязателен,
    только когда этот режим реально выбран (KERBEROS_MODE=python)."""

    def __init__(self) -> None:
        try:
            import gssapi
        except ImportError as exc:  # pragma: no cover — зависит от системных библиотек
            raise RuntimeError(
                "KERBEROS_MODE=python требует установленный пакет python-gssapi "
                "(и системную библиотеку Kerberos на сервере) — см. deploy/redos8/README.md"
            ) from exc

        if not settings.kerberos_server_hostname:
            raise RuntimeError(
                "KERBEROS_SERVER_HOSTNAME не задан — не могу собрать SPN для приёма тикетов "
                "(заполняется, когда IT выдаст keytab под конкретный сервер)"
            )
        if not settings.kerberos_keytab_path:
            raise RuntimeError("KERBEROS_KEYTAB_PATH не задан — нечем проверять тикеты")

        os.environ["KRB5_KTNAME"] = settings.kerberos_keytab_path

        self._gssapi = gssapi
        service_name = gssapi.Name(
            f"HTTP@{settings.kerberos_server_hostname}",
            gssapi.NameType.hostbased_service,
        )
        try:
            self._server_creds = gssapi.Credentials(name=service_name, usage="accept")
        except gssapi.exceptions.GSSError as exc:
            raise RuntimeError(
                f"Не удалось загрузить keytab {settings.kerberos_keytab_path} для SPN "
                f"HTTP@{settings.kerberos_server_hostname}: {exc}"
            ) from exc

    def authenticate(self, authorization_header: str | None) -> str:
        """Возвращает логин (без домена) аутентифицированного принципала
        или бросает AuthChallengeError/ForbiddenError."""
        if not authorization_header:
            raise AuthChallengeError(
                "Требуется Kerberos-аутентификация", www_authenticate=NEGOTIATE
            )
        scheme, _, token_b64 = authorization_header.partition(" ")
        if scheme.lower() != NEGOTIATE.lower() or not token_b64:
            raise AuthChallengeError(
                "Ожидается заголовок Authorization: Negotiate <token>",
                www_authenticate=NEGOTIATE,
            )
        try:
            token = base64.b64decode(token_b64.strip())
        except (ValueError, binascii.Error) as exc:
            raise ForbiddenError("Некорректный формат Kerberos-токена") from exc

        gssapi = self._gssapi
        ctx = gssapi.SecurityContext(creds=self._server_creds, usage="accept")
        try:
            ctx.step(token)
        except gssapi.exceptions.GSSError as exc:
            logger.warning("Kerberos: не удалось проверить SPNEGO-тикет: %s", exc)
            raise ForbiddenError("Не удалось проверить Kerberos-тикет") from exc

        if not ctx.complete:
            # На практике браузер/curl --negotiate с валидным TGT укладывается
            # в один обмен. Многораундовая негоциация потребовала бы вернуть
            # клиенту continuation-токен через WWW-Authenticate и ждать
            # повторного запроса — в текущей схеме (простой заголовок ->
            # 200/ошибка на один запрос) это не поддержано.
            raise ForbiddenError("Kerberos-рукопожатие не завершилось за один обмен")

        return principal_to_login(str(ctx.initiator_name))


_gssapi_provider: KerberosGSSAPIAuthProvider | None = None


def get_gssapi_provider() -> KerberosGSSAPIAuthProvider:
    """Синглтон — Credentials из keytab грузятся один раз при первом
    обращении (или на старте приложения, см. main.py), не на каждый запрос."""
    global _gssapi_provider
    if _gssapi_provider is None:
        _gssapi_provider = KerberosGSSAPIAuthProvider()
    return _gssapi_provider
