# Планирование отпусков сотрудников

Веб-приложение для подачи и согласования отпусков: графический выбор периода,
недоступные периоды (учёба и т.п.), контроль загруженности отделов, оргструктура
из внешней системы, управляемые ограничения и льготы. Полное описание архитектуры
и поэтапный план — см. план реализации (сохранён в ходе сессии планирования).

Стек: FastAPI + PostgreSQL (бэкенд), React + TypeScript (фронтенд), SSO/OIDC.

## Быстрый старт (локальная разработка)

### Бэкенд

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"

docker compose up -d db
.venv/bin/alembic upgrade head
.venv/bin/python -m scripts.seed_dev_data

.venv/bin/uvicorn app.main:app --reload
```

API-документация: http://localhost:8000/docs

### Фронтенд

```bash
cd frontend
npm install
npm run dev
```

Приложение: http://localhost:5173 — в dev-режиме предлагает выбрать тестового
пользователя вместо реального SSO (см. `AUTH_PROVIDER=dev` в `backend/app/config.py`).

### Тесты

```bash
cd backend
.venv/bin/pytest
```

## Статус

- **Phase 0 (готово):** каркас проекта, БД, dev-аутентификация, оргструктура (read-only просмотр).
- Phase 1–5: см. план реализации.
