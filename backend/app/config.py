from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    admin_email: str = "admin@localhost"
    admin_password: str = "admin"
    secret_key: str = "dev-secret-change-me"
    database_url: str = "sqlite:///./data/lca.sqlite3"
    cors_origins: str = "http://localhost:5173"
    archive_path: str = ""
    ef31_method_path: str = ""
    public_signup: bool = True
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@localhost"
    app_base_url: str = "http://localhost:5173"
    session_https_only: bool = False
    demo_seed: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()


def ensure_data_dir(database_url: str) -> None:
    if database_url.startswith("sqlite"):
        raw = database_url.split("///", 1)[-1]
        path = Path(raw)
        if path.parent and str(path.parent) not in {".", ""}:
            path.parent.mkdir(parents=True, exist_ok=True)
