from dataclasses import dataclass
from functools import lru_cache
import os


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str
    database_url: str
    db_connect_timeout_seconds: int
    cors_origins: list[str]
    work_order_generator_provider: str
    work_order_generator_fallback_provider: str
    gemini_api_key: str | None
    gemini_model: str
    openai_api_key: str | None
    openai_model: str


def parse_csv_env(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "Gongjangjigi API"),
        app_env=os.getenv("APP_ENV", "local"),
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql://gongjang:gongjang@localhost:5432/gongjang",
        ),
        db_connect_timeout_seconds=int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "3")),
        cors_origins=parse_csv_env(
            os.getenv("CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173")
        ),
        work_order_generator_provider=os.getenv("WORK_ORDER_GENERATOR_PROVIDER", "template"),
        work_order_generator_fallback_provider=os.getenv("WORK_ORDER_GENERATOR_FALLBACK_PROVIDER", "template"),
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
    )
