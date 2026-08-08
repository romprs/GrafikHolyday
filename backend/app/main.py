from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.routers import (
    admin_sync,
    auth_dev,
    blocked_periods,
    calendar,
    leave_balances,
    leave_requests,
    org_load,
    org_units,
    restriction_settings,
    users,
)

app = FastAPI(title="Планирование отпусков", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(users.router)
app.include_router(org_units.router)
app.include_router(auth_dev.router)
app.include_router(leave_requests.router)
app.include_router(leave_balances.router)
app.include_router(blocked_periods.router)
app.include_router(calendar.router)
app.include_router(restriction_settings.router)
app.include_router(admin_sync.router)
app.include_router(org_load.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
