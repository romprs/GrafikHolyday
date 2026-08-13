from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://vacation:vacation@localhost:5432/vacation"
    auth_provider: str = "dev"  # "dev" | "oidc" | "kerberos"
    log_level: str = "INFO"

    oidc_issuer: str | None = None
    oidc_client_id: str | None = None
    oidc_jwks_url: str | None = None

    # Боевая схема входа — Kerberos/SPNEGO через AD-домен corp.amurgpz.ru
    # (OIDC выше сохранён на случай, если понадобится позже, но сейчас не
    # тот протокол). kerberos_server_hostname — конкретное имя сервера,
    # на которое заходят пользователи (часть SPN вида HTTP/<hostname>@REALM);
    # заполняется, когда IT выдаст keytab под конкретный хост — до этого
    # момента kerberos-провайдер не может быть включён.
    kerberos_realm: str = "CORP.AMURGPZ.RU"
    kerberos_server_hostname: str | None = None
    kerberos_keytab_path: str | None = None

    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
