"""Клиент и парсер источника учебных планов (недоступные периоды сотрудников).

Формат ответа предварительный (контракт с реальным источником согласован
частично) — список объектов вида
    [{"<табельный номер>": [{"ПрограммаОбучения": "...", "Дата": "24.10.2024 0:00:00",
                              "КолВоЧасов": "16"}, ...]}, ...]
Один и тот же parse_entries используется и для файла целиком (все
сотрудники разом, режим "file"), и для склеенных ответов HTTP-источника
(по одному сотруднику за раз, режим "http") — структура записи одинаковая.
"""

import logging
import os
import ssl
import tempfile
from datetime import date, datetime

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from pydantic import BaseModel

logger = logging.getLogger(__name__)


def _ssl_context_from_pfx(pfx_path: str, pfx_password: str | None, verify_tls: bool) -> ssl.SSLContext:
    """Строит SSLContext с клиентским сертификатом из .pfx/.p12 (PKCS#12) —
    httpx/stdlib ssl не умеют грузить PKCS#12 напрямую, поэтому парсим его
    через cryptography и на время (временные файлы удаляются сразу после
    load_cert_chain) отдаём как обычную пару PEM cert+key."""
    with open(pfx_path, "rb") as f:
        pfx_data = f.read()

    try:
        private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
            pfx_data, pfx_password.encode() if pfx_password else None
        )
    except Exception as exc:  # noqa: BLE001 — неверный пароль/битый файл, хотим понятное сообщение
        raise RuntimeError(f"Не удалось прочитать сертификат {pfx_path}: {exc}") from exc

    if private_key is None or certificate is None:
        raise RuntimeError(f"Файл {pfx_path} не содержит закрытого ключа и/или сертификата")

    cert_pem = certificate.public_bytes(serialization.Encoding.PEM)
    for extra in additional_certs or []:
        cert_pem += extra.public_bytes(serialization.Encoding.PEM)
    key_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )

    context = ssl.create_default_context()
    if not verify_tls:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    cert_fd, cert_file = tempfile.mkstemp(suffix=".pem")
    key_fd, key_file = tempfile.mkstemp(suffix=".pem")
    try:
        with os.fdopen(cert_fd, "wb") as f:
            f.write(cert_pem)
        with os.fdopen(key_fd, "wb") as f:
            f.write(key_pem)
        context.load_cert_chain(cert_file, key_file)
    finally:
        os.unlink(cert_file)
        os.unlink(key_file)
    return context


class StudyPeriodEntryDTO(BaseModel):
    employee_code: str
    program_name: str
    date: date
    hours: float


def _parse_date(raw: str) -> date:
    return datetime.strptime(raw.strip(), "%d.%m.%Y %H:%M:%S").date()


def parse_entries(raw: list[dict]) -> list[StudyPeriodEntryDTO]:
    entries: list[StudyPeriodEntryDTO] = []
    for block in raw:
        if not isinstance(block, dict):
            continue
        for employee_code, programs in block.items():
            for item in programs or []:
                entries.append(
                    StudyPeriodEntryDTO(
                        employee_code=str(employee_code),
                        program_name=item["ПрограммаОбучения"],
                        date=_parse_date(item["Дата"]),
                        hours=float(item.get("КолВоЧасов") or 0),
                    )
                )
    return entries


class StudyPeriodsClient:
    """Одна заявка на сотрудника — контракт источника отдаёт план по одному
    табельному номеру за раз (см. Employee в query-параметрах).

    Авторизация — Basic (login/password) и/или клиентский сертификат
    (cert_path на .pfx/.p12-файл, лежащий на диске сервера + опциональный
    пароль к нему). Сертификат парсится один раз при создании клиента, а
    не на каждый запрос — операция не бесплатная и сотрудников может быть
    несколько тысяч."""

    def __init__(
        self,
        base_url: str,
        login: str = "",
        password: str = "",
        verify_tls: bool = True,
        timeout: float = 60.0,
        cert_path: str | None = None,
        cert_password: str | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._auth = httpx.BasicAuth(login, password) if login else None
        self._timeout = timeout
        self._verify: bool | ssl.SSLContext = verify_tls
        if cert_path:
            self._verify = _ssl_context_from_pfx(cert_path, cert_password, verify_tls)

    def fetch_raw(self, employee_code: str, period_from: date, period_to: date) -> list[dict]:
        params = {
            "type": "JSON",
            "Period1": f"{period_from:%d.%m.%Y} 0:00:00",
            "Period2": f"{period_to:%d.%m.%Y} 23:59:59",
            "Employee": employee_code,
        }
        logger.info(
            "Запрос к источнику недоступных периодов (1С): GET %s, табельный номер=%s, период=%s..%s",
            self._base_url,
            employee_code,
            period_from,
            period_to,
        )
        try:
            response = httpx.get(
                self._base_url,
                params=params,
                auth=self._auth,
                verify=self._verify,
                timeout=self._timeout,
            )
        except httpx.RequestError as exc:
            logger.error(
                "Не удалось соединиться с источником недоступных периодов (%s, табельный номер=%s): %s",
                self._base_url,
                employee_code,
                exc,
            )
            raise RuntimeError(f"Не удалось соединиться с {self._base_url}: {exc}") from exc

        logger.info(
            "Ответ от источника недоступных периодов (табельный номер=%s): HTTP %s, %d байт",
            employee_code,
            response.status_code,
            len(response.content),
        )
        if response.is_error:
            body_preview = response.text[:500]
            logger.error(
                "Источник недоступных периодов вернул ошибку: GET %s (табельный номер=%s) -> HTTP %s. Тело ответа: %s",
                self._base_url,
                employee_code,
                response.status_code,
                body_preview,
            )
            raise RuntimeError(
                f"Источник ответил HTTP {response.status_code} на запрос по табельному номеру {employee_code}"
                + (f": {body_preview}" if body_preview else "")
            )

        try:
            data = response.json()
        except ValueError as exc:
            body_preview = response.text[:500]
            logger.error(
                "Не удалось разобрать ответ источника недоступных периодов (табельный номер=%s) как JSON: %s. Тело ответа (начало): %s",
                employee_code,
                exc,
                body_preview,
            )
            raise RuntimeError(
                f"Ответ источника (табельный номер={employee_code}) не является корректным JSON: {exc}"
            ) from exc
        return data if isinstance(data, list) else [data]
