from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://vacation:vacation@localhost:5432/vacation"
    auth_provider: str = "dev"  # "dev" | "oidc"
    log_level: str = "INFO"

    oidc_issuer: str | None = None
    oidc_client_id: str | None = None
    oidc_jwks_url: str | None = None

    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
