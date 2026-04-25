from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "development"
    api_port: int = 8100
    frontend_origin: str = "http://localhost:5173"
    database_url: str = "sqlite:///./niche.db"
    jwt_secret: str = "change-me"
    jwt_expires_minutes: int = 1440
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    oauth_redirect_base: str = "http://localhost:8100"
    rate_limit_per_minute: int = 120

    @property
    def oauth_enabled(self) -> bool:
        return bool(
            (self.google_client_id and self.google_client_secret)
            or (self.github_client_id and self.github_client_secret)
        )


@lru_cache
def get_settings() -> Settings:
    return Settings(
        env=_env("NICHE_ENV", "development"),
        api_port=int(_env("NICHE_API_PORT", "8100")),
        frontend_origin=_env("NICHE_FRONTEND_ORIGIN", "http://localhost:5173"),
        database_url=_env("NICHE_DATABASE_URL", "sqlite:///./niche.db"),
        jwt_secret=_env("NICHE_JWT_SECRET", "change-me"),
        jwt_expires_minutes=int(_env("NICHE_JWT_EXPIRES_MINUTES", "1440")),
        google_client_id=_env("NICHE_GOOGLE_CLIENT_ID", ""),
        google_client_secret=_env("NICHE_GOOGLE_CLIENT_SECRET", ""),
        github_client_id=_env("NICHE_GITHUB_CLIENT_ID", ""),
        github_client_secret=_env("NICHE_GITHUB_CLIENT_SECRET", ""),
        oauth_redirect_base=_env("NICHE_OAUTH_REDIRECT_BASE", "http://localhost:8100"),
        rate_limit_per_minute=int(_env("NICHE_RATE_LIMIT_PER_MINUTE", "120")),
    )


def _env(key: str, default: str) -> str:
    import os

    return os.getenv(key, default)
