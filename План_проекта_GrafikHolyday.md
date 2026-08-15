# Программа планирования отпусков сотрудников

## Статус: Phases 0–5 готовы, реальные интеграции подключены, Phase 6 (доводка) в процессе

Ниже — обновлённый план с учётом всего, что реально реализовано поверх
исходного дизайна (описан в разделах ниже) и того, что подтверждено
пользователем в процессе демо и обратной связи. Актуальный код живёт в
репозитории `romprs/grafikholyday` (GitHub уведомляет, что канонический
путь теперь `romprs/GrafikHolyday` — редирект работает, репозиторий не
переименовывался в смысле доступа), ветка `claude/vacation-planning-program-4tcouk`.

**Доставка кода:** прямой `git push` из рабочей среды в `romprs/grafikholyday`
теперь работает (проверено) — рабочая среда содержит отдельный клон в
`/workspace/grafikholyday` с remote `origin` на GitHub и remote `local-work`
на основной рабочий чекаут; изменения делаются в основном чекауте,
переносятся туда через `git fetch local-work` + `git merge --ff-only`,
затем `git push origin`. `git push`/GitHub MCP из основного рабочего
чекаута в `romprs/work` по-прежнему возвращают `403` (интеграции не
выдан доступ на запись в этот репозиторий) — `romprs/work` для этого
проекта не используется, это отдельный (пустой) репозиторий.

## Контекст (не изменился)

Компании нужен веб-инструмент для подачи и согласования отпусков, который решает несколько проблем одновременно: сотрудники должны выбирать период визуально и не иметь возможности попасть в дни, когда отдел занят учёбой/сборами; руководители должны видеть нагрузку по отделам, чтобы не допускать одновременного ухода в отпуск большей части команды; HR должен иметь возможность гибко включать/выключать ограничения и учитывать сотрудников со льготами, на которых эти ограничения не действуют. Структура компании (отделы, управления, сотрудники, льготы) — синхронизация из внешней корпоративной системы (реальный REST/OData-контракт подключён, см. ниже).

**Стек:** Python (FastAPI) + PostgreSQL (SQLAlchemy + Alembic) на бэкенде, React + TypeScript (Vite) на фронте. Аутентификация в проде пока — dev-режим (выбор тестового пользователя), но **Kerberos/SPNEGO**-провайдер (прозрачный вход для доменных Windows-машин через AD-домен `corp.amurgpz.ru`) уже реализован и ждёт только keytab/hostname от IT (`AUTH_PROVIDER=kerberos` в `.env`) — не OIDC/SAML, как предполагалось изначально (`restriction_settings.auth_configuration` и `oidc_provider.py` под OIDC остались нетронутой заглушкой, актуальный провайдер — `app/auth/kerberos_provider.py`, см. Phase 6.11). Логин пользователя = часть email до `@` (сопоставление с уже существующим `User.email`, который синк заполняет как `login@corp.amurgpz.ru`).

**Ключевые решения:**
- % загруженности отдела = доля сотрудников юнита в отпуске в конкретный день, пороги (жёлтый/красный) настраиваются через `restriction_settings` (`department_load_thresholds`)
- Дни отпуска — календарные (не рабочие)
- Согласование заявки — руководителем прямого отдела сотрудника, либо делегатом (см. делегирование ниже)
- Все ограничения управляемые через настройки, с полным исключением сотрудников с `has_benefits=true` (кроме правила пересечения своих же периодов — оно не про льготы)
- Оргструктура — произвольная глубина вложенности, импорт по REST/OData из внешней системы, read-only в приложении для обычных ролей, CRUD доступен `hr_admin`
- Планирование ведётся на конкретный **плановый год** (`restriction_settings.planning_year`), влияет на баланс, пикер и дашборд загруженности
- **Каждая внешняя интеграция независима**: своя запись в `restriction_settings`, свой `sync_runs.kind`, свой admin-роутер. Синхронизация оргструктуры/сотрудников (drx, `GetDepartments`/`GetEmployeers`) и синхронизация дней отпуска/льгот (другая система, `hrm_new3`, `GetVacationDaysCount` по табельному номеру) — два independent процесса, специально спроектированные так, чтобы не затирать данные друг друга (`has_benefits: bool | None` — `None` значит "источник не знает, не трогать")

## Модель данных (PostgreSQL) — как есть сейчас

- **`org_units`** (id, parent_id→org_units, name, unit_kind, head_user_id→users, is_active) — adjacency list, `WITH RECURSIVE` для обхода. `use_alter=True` на `head_user_id` (циклическая FK с `users`). CRUD доступен `hr_admin` (создание/редактирование/деактивация).
- **`users`** (id, email, full_name, org_unit_id, has_benefits, is_active, employee_code, last_synced_at). `employee_code` (табельный номер) — уникальный, nullable, ключ связи с внешними системами (учебные планы, дни отпуска). Роль руководителя вычисляется (`head_user_id` какого-то `org_unit` == этот user), не хранится. CRUD доступен `hr_admin`.
- **`user_roles`** (user_id, role='hr_admin') — единственная локальная (не синковая) таблица ролей; управляется через страницу «Роли».
- **`leave_delegations`** (id, scope[user/org_unit], delegate_user_id, target_user_id, target_org_unit_id, is_active, created_by, created_at, revoked_at) — делегирование права согласования: либо "сотрудник за сотрудника" (`scope=user`), либо "сотрудник за всё подразделение" (`scope=org_unit`, каскадом на все вложенные юниты). Управляется через страницу «Делегирование».
- **`leave_types`** (id, code, name_ru, is_active) — сид `vacation`.
- **`leave_requests`** (id, user_id, leave_type_id, date_from, date_to, comment, status, reviewer_id, review_comment, submitted_at, reviewed_at, cancelled_at, cancelled_by, submission_id).
  Статусы: `draft` → `pending_approval` → `approved`/`rejected`, либо `cancelled` из pending/approved.
  **`draft` — активно используемый статус**: период сохраняется в БД сразу при добавлении в форме, а не хранится в состоянии компонента — переживает переключение вкладок/перезагрузку. Отправка на согласование (`submit_drafts`) переводит все черновики года разом в `pending_approval` одной `submission_id`-группой, но **только если их суммарная длительность точно равна остатку баланса**. Согласование/отклонение/отмена — атомарно по всей группе (`submission_id`), не по отдельным периодам.
- **`leave_balances`** (user_id, year, accrued_days, carried_over_days, updated_by) — `used`/`remaining` вычисляются на лету. Остаток для новой заявки/черновика учитывает `approved + pending_approval + draft` (чтобы нельзя было "перекредитовать" баланс). `accrued_days` обновляется синхронизацией дней отпуска, `carried_over_days` — никогда автоматически (только вручную HR).
- **`blocked_periods`** (id, date_from, date_to, reason, scope[global/org_unit/user], org_unit_id, user_id, is_active, created_by) — наследование по дереву org_unit. Источник для `scope=org_unit` может приходить из внешней системы учебных планов (см. `study_periods_source`).
- **`restriction_settings`** (key PK, enabled, params jsonb, description) — сиды: `min_leave_duration`, `blocked_period_enforcement`, `department_load_thresholds`, `leave_balance_limit`, `own_overlap_check`, `planning_year`, `vacation_bonus`, `auth_configuration`, `external_source_connection` (оргструктура+сотрудники, drx), `study_periods_source` (учебные планы 1С), `vacation_days_source` (дни отпуска+льготы, hrm_new3).
- **`external_id_mappings`**, **`sync_runs`** (с дискриминатором `kind`: `org_directory`/`study_periods`/`vacation_days`), **`sync_change_log`** — общий движок синхронизации + журнал изменений для всех трёх интеграций.
- **`audit_log`** (entity_type, entity_id, action, performed_by, reason, before_state, after_state) — пишется при HR admin-override и при HR CRUD над `org_units`/`users`.

## Структура бэкенда (FastAPI) — как есть сейчас

```
app/
  main.py, config.py, database.py, dependencies.py
  auth/            interface.py (AuthProvider ABC), dev_provider.py,
                    kerberos_provider.py (боевая схема — Kerberos/SPNEGO,
                    см. Phase 6.11: resolve_login сопоставляет логин с
                    User.email, KerberosGSSAPIAuthProvider — режим
                    KERBEROS_MODE=python; login_from_trusted_header —
                    режим KERBEROS_MODE=nginx). oidc_provider.py — заглушка
                    под OIDC, больше не актуальна (не тот протокол),
                    оставлена нетронутой на случай, если пригодится позже.
  models/          org_unit, user, user_role, leave_delegation, leave_type,
                    leave_request, leave_balance, blocked_period,
                    restriction_settings, external_id_mapping, sync (SyncRun,
                    SyncChangeLog, KIND_*), audit_log
  schemas/         зеркалит models/
  routers/         org_units (+CRUD), users, admin_users (CRUD сотрудников,
                    employee-code), leave_requests, leave_balances,
                    blocked_periods, calendar, org_load, restriction_settings,
                    admin_sync (оргструктура+сотрудники), admin_study_periods,
                    admin_vacation_days, delegations, audit, roles
  services/
    permissions.py                  — резолвинг роли (employee/manager/hr_admin)
    leave_request_service.py        — create_draft/list_drafts/delete_draft/
                                       submit_drafts, list_own, list_team_leave, cancel
    approval_service.py             — approve/reject по submission_id, admin-override
                                       → audit_log, учитывает делегирование
    delegation_service.py           — create/revoke/list, резолвинг "кто может
                                       согласовывать за X" (прямой руководитель
                                       + активные делегации user/org_unit-scope
                                       с каскадом по дереву)
    leave_balance_service.py        — get_summary, get_remaining_for_new_request
    org_unit_service.py             — recursive CTE: descendants(id), ancestors(id)
    org_load_service.py             — get_org_load (агрегат по дням), get_org_leave_detail
                                       (сырые employees+leaves для интерактивного дашборда)
    blocked_period_service.py       — CRUD + эффективные блокировки
    restriction_settings_service.py — включая get_planning_year()
    user_admin_service.py           — HR CRUD над users/org_units, employee_code
    audit_service.py
    sync_service.py                 — общий 3-pass upsert (org_units → users →
                                       head_user_id) через external_id_mappings,
                                       kind=org_directory
    study_period_sync_service.py    — синхронизация недоступных периодов,
                                       kind=study_periods
    vacation_days_sync_service.py   — синхронизация accrued_days + has_benefits
                                       по employee_code, kind=vacation_days,
                                       НЕ трогает carried_over_days
    validation/engine.py            — прогоняет включённые правила, льготники
                                       пропускают exemptable-правила
    validation/min_duration_rule.py
    validation/blocked_period_rule.py
    validation/leave_balance_rule.py
    validation/own_overlap_rule.py  — не exemptable (физическое ограничение)
  integrations/    org_directory.py (реальный клиент: GetDepartments +
                    GetEmployeers, Basic Auth), study_periods.py, vacation_days.py
                    (реальный клиент: GetVacationDaysCount по tabnum)
  sync/            interface.py (ExternalDirectoryClient ABC), dto.py
                    (ExternalOrgUnitDTO/ExternalUserDTO), fake_client.py (dev),
                    scheduler.py
alembic/versions/... (полная цепочка миграций Phase 0 → делегирование →
                    employee_code → sync kind → vacation_days_source, проверена
                    "upgrade head" с нуля на реальном Postgres 16)
tests/unit/ — 186 тестов, pytest + SQLite in-memory (плюс пара тестов
                    на FastAPI TestClient — auth_challenge_error)
```

**Дашборд загруженности отдела** — единая таблица (`OrgLoadDashboardPage`): месяцы по строкам, дни по столбцам, заполнены только непустые ячейки (есть кто-то в отпуске), клик по ячейке показывает список отпускников. Фильтр по роли (руководитель/специалист/все), поиск по фамилии (с 4 букв), произвольный выбор сотрудников для точечного анализа пересечений, согласование прямо с дашборда. Бэкенд отдаёт сырые данные (`get_org_leave_detail`) — вся агрегация и раскраска (`green`/`yellow`/`red` по порогам) считается на фронте.

**Блокировка правок после согласования** — `approve/reject` только из `pending_approval`, атомарно по всей группе `submission_id`; после `approved` доступна только отмена (руководителем/делегатом или самим сотрудником — по правилам). Исключение — `PATCH /leave-requests/{id}/admin-override` (`hr_admin`, обязательный `reason`, пишет в `audit_log`).

**Делегирование** — два независимых сценария: точечное "сотрудник за сотрудника" и "сотрудник за всё подразделение" (каскадом на вложенные юниты — чтобы не заводить делегацию на каждый отдел вручную). Учитывается наравне с прямым руководством во всех местах, где резолвится "кто может согласовать".

## Структура фронтенда (React + TS) — как есть сейчас

- `api/` — типизированный клиент (`apiFetch`, `ApiError` со структурой `{code, message_ru, params}`)
- `auth/AuthContext` — dev-режим (выбор пользователя из списка), `X-Dev-User-Id` заголовок. Хедер (ФИО + роль + кнопка «Выйти» в одну строку, «Выйти» справа) общий для всех вкладок.
- `pages/`: RequestFormPage (план отпуска — черновики + отправка), MyRequestsPage (календарь + отмена целиком), ApprovalQueuePage, BlockedPeriodsPage, OrgDirectoryPage (объединяет бывшие OrgUnitsPage/EmployeesPage/RolesPage — таблица подразделений+сотрудников: сворачивание по узлам, фильтры ФИО/роль/подразделение с автораскрытием пути, инлайн-редактирование сотрудника HR admin'ом — подразделение/льготы/таб.номер/баланс/роль, руководитель всегда первой строкой в подразделении, деактивированные подразделения видны HR приглушённым цветом с кнопкой реактивации), OrgLoadDashboardPage (вкладка «Отпуска подразделений», бывшая «Загруженность отделов» — список сотрудников с поиском слева, график месяцы×дни по центру, описание дня по клику справа), IntegrationsSettingsPage (настройки всех трёх внешних источников: оргструктура/сотрудники, учебные планы, дни отпуска+льготы — enable/URL/auth, ручной запуск, история запусков, плюс загрузка оргструктуры/сотрудников файлом), RestrictionSettingsPage, AllRequestsPage, AuditLogPage, DelegationsPage (создание/отзыв делегаций user- и org_unit-scope; делегат для руководителя ограничен его веткой подчинения, поиск по фамилии). TeamCalendarPage удалена — дублировала OrgLoadDashboardPage.
- Поиск по фамилии (Delegations, OrgLoadDashboard) — helper `surname()` берёт **первое** слово ФИО, т.к. в приложении ФИО хранится как «Фамилия Имя Отчество» (не Western-порядок) — эта деталь один раз уже была багом (брали последнее слово), исправлено.
- `components/DateRangePicker` — обёртка над `react-day-picker` v9, показывает **все 12 месяцев планового года одновременно** (`numberOfMonths={12}`, `disableNavigation`). `disabled` = недоступные периоды + уже добавленные в план черновики
- Серверное состояние — TanStack Query, инвалидация кэша между заявками/балансом/календарём/дашбордом
- Вся текстовая часть на русском (без i18n-библиотеки — строки хардкожены по-русски прямо в компонентах)

## Поэтапный план сборки — статус

1. **Phase 0 — Каркас и авторизация-заглушка.** ✅ Готово.
2. **Phase 1 — CRUD заявок + согласование.** ✅ Готово (позже переработано в draft-flow, см. Phase 5.2).
3. **Phase 2 — Календарь, графический пикер, блокировки.** ✅ Готово.
4. **Phase 3 — Синхронизация оргструктуры + дашборд загруженности.** ✅ Готово (дашборд позже полностью переделан; клиент позже заменён на реальный, см. Phase 6).
5. **Phase 4 — Управляемые ограничения, льготы, аудит.** ✅ Готово.
6. **Phase 5 — Обратная связь по демо + полировка.** ✅ Готово:
   - Баланс на форме заявки, лимит по остатку, несколько периодов в заявке, плановый год как настройка, страница «Сотрудники», страница «Роли»
   - Дашборд загруженности переделан в единую таблицу месяцы×дни с фильтрами/поиском/произвольным выбором сотрудников, согласование прямо с дашборда
   - Черновики периодов (`draft`), отправка/согласование/отмена атомарно по группе `submission_id`
   - Недоступные периоды из внешнего источника (учебные планы 1С), с областью «Сотрудник»
   - Бонус к отпуску (порог "от 14 дней", один период на план)
   - Офлайн-развёртывание на РЕД ОС 8 (`deploy/redos8`: install.sh, nginx, systemd-unit, сборка бандла)
7. **Phase 6 — Реальные интеграции + управление структурой.** 🔶 В процессе:
   - ✅ 6.1 Роли: делегирование заявок (user + org_unit scope с каскадом), видимость вкладок/оргструктуры по роли
   - ✅ 6.2 HR: CRUD подразделений и сотрудников прямо в приложении
   - ✅ 6.3 Реальный клиент источника оргструктуры (`GetDepartments`, drx, Basic Auth) вместо `fake_client`
   - ✅ 6.4 Реальный клиент синхронизации сотрудников (`GetEmployeers`, тот же источник) — email/employee_code/org_unit по логину/tabnum/podrid, только числовые табельные номера, сотрудники без логина пока пропускаются
   - ✅ 6.5 Отдельная синхронизация дней отпуска и льготы (`GetVacationDaysCount`, другая система hrm_new3, запрос по каждому tabnum) — независимая настройка/роутер/история запусков, не пересекается с 6.4 по владению `has_benefits`. Запрашивает внешний источник строго по одному сотруднику за раз (последовательно, без параллелизма) — на ~3900 реальных сотрудниках это может быть заметно долгим синхронным HTTP-запросом от кнопки «Синхронизировать сейчас»; если станет проблемой на реальных объёмах — сделать синк фоновым и/или распараллелить запросы (не сделано, пользователь пока не просил).
   - ✅ 6.6 Фикс сопоставления сотрудников с подразделениями при раздельной загрузке (sync_service резолвил ссылки только по текущей выгрузке, не заглядывая в уже существующие external_id_mappings) + скрипт чистки `reset_org_directory_sync.py`
   - ✅ 6.7 Загрузка оргструктуры/сотрудников файлом (без ожидания рабочего HTTP-источника) — `POST /admin/sync/import`, тот же external_system, что у HTTP-клиента
   - ✅ 6.8 Единая вкладка «Оргструктура и сотрудники» (см. OrgDirectoryPage выше) вместо трёх разрозненных страниц
   - ✅ 6.9 Делегирование: делегат для руководителя ограничен его веткой подчинения + поиск по фамилии
   - ✅ 6.10 Убрана вкладка «Календарь отдела» (дублировала «Загруженность отделов»); та переименована в «Отпуска подразделений» и переверстана (сотрудники слева, график по центру, детали дня справа)
   - ✅ 6.11 Реальная аутентификация — **Kerberos/SPNEGO** через AD-домен `corp.amurgpz.ru`, логин = локальная часть Kerberos-принципала/email (сопоставляется с `User.email` через `ILIKE 'login@%'`, `app/auth/kerberos_provider.resolve_login`). Реализованы **оба варианта** проверки SPNEGO-тикета, переключаются `KERBEROS_MODE` без правки кода:
     - `KERBEROS_MODE=nginx` — тикет проверяет nginx (модуль с директивами `auth_gssapi_*`, образец — `deploy/redos8/nginx-gssapi.conf.example`), бэкенд читает уже подтверждённый логин из заголовка `KERBEROS_TRUSTED_HEADER` (по умолчанию `X-Remote-User`) — `app/auth/kerberos_provider.login_from_trusted_header`. Бэкенд Kerberos не касается вообще (ни keytab, ни python-gssapi).
     - `KERBEROS_MODE=python` — тикет проверяет сам бэкенд через `python-gssapi` (`app/auth/kerberos_provider.KerberosGSSAPIAuthProvider`, ленивый импорт gssapi + keytab из `KERBEROS_KEYTAB_PATH`, SPN `HTTP/<KERBEROS_SERVER_HOSTNAME>@<KERBEROS_REALM>`); при отсутствии Authorization-заголовка отдаёт `401 + WWW-Authenticate: Negotiate` (новый `AuthChallengeError` в `app/core/exceptions.py`) — без этого браузер не станет присылать SPNEGO-токен. Провалидировано на реальном uvicorn (fail-fast на старте при отсутствии `gssapi`/незаполненном hostname; корректный 200/403 для nginx-режима с реальным HTTP-запросом).
     - Оба режима покрыты тестами (`tests/unit/test_kerberos_provider.py`, `tests/unit/test_auth_challenge_error.py`).
     - `python-gssapi` — опциональная зависимость (`kerberos` extra в `pyproject.toml`), без готовых manylinux-колёс на PyPI; для офлайн-бандла нужно собрать колесо отдельно (см. `deploy/redos8/README.md`) — `install.sh` подхватывает его из `wheelhouse/`, если найден, иначе просто пропускает (не ошибка).
     - **Открыто**: не решено, какой именно `KERBEROS_MODE` использовать в проде — зависит от того, есть ли на сервере nginx с GSSAPI-модулем (см. «Открытые допущения» ниже), плюс от IT ещё нужны сам keytab, `KERBEROS_SERVER_HOSTNAME` и подтверждение realm.
   - ⬜ Планировщик автозапуска синхронизаций по расписанию (сейчас только ручной запуск через UI; `poll_interval_minutes` в настройках есть, но не используется)
   - ⬜ Playwright smoke-тест как часть репозитория (пока проверки делаются вручную на реальном Postgres в песочнице, не закоммичены)
   - ⬜ Категория сотрудника (`kat`: руководитель/специалист/рабочий) из `GetEmployeers` — в текущей реализации не сохраняется (роль руководителя уже вычисляется через `head_user_id`, назначение остальных явно не запрашивалось)

## Открытые допущения

- Есть ли у внешней системы гарантированно один `head_user_id` на юнит, или нужен локальный override — подтверждено реальными данными (`GetDepartments`), полей достаточно, override не потребовался.
- Категория сотрудника (`kat`) из `GetEmployeers` не используется — уточнить у пользователя, нужна ли (сейчас роль "руководитель" полностью выводится из `org_units.head_user_id`).
- `romprs/work` — отдельный, не связанный с проектом репозиторий; писать туда для этого проекта не нужно (ошибочно использовался один раз из-за автоматически подставленного репозитория в рабочей среде, исправлено после уточнения пользователя).
- **Аутентификация — Phase 6.11 реализована (оба варианта, см. выше), но включение в проде ждёт две вещи от IT:**
  1. Собран ли nginx на РЕД ОС 8 с поддержкой GSSAPI/SPNEGO — определяет, какой `KERBEROS_MODE` реально доступен (`nginx` или `python`); код и конфиги готовы под оба, переключение не требует правок кода.
  2. Сам keytab-файл, конкретный `KERBEROS_SERVER_HOSTNAME` (сервер, на который заходят пользователи) — реалм `CORP.AMURGPZ.RU` пользователь подтвердил.
  До получения этого от IT `AUTH_PROVIDER` в `.env` остаётся `dev`.
