from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["health"])


def health() -> dict:
    return {"data": {"status": "ok", "service": get_settings().app_name}}


@router.get("/health")
def read_health() -> dict:
    return health()


@router.get("/api/v1/health/db")
def read_db_health() -> dict:
    settings = get_settings()

    try:
        import psycopg

        with psycopg.connect(
            settings.database_url,
            connect_timeout=settings.db_connect_timeout_seconds,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("select 1")
                cur.fetchone()
                cur.execute("select exists(select 1 from pg_extension where extname = 'vector')")
                has_vector = bool(cur.fetchone()[0])
    except Exception as exc:
        return {
            "data": {
                "status": "error",
                "database": "unavailable",
                "pgvector": "unknown",
                "message": str(exc),
            }
        }

    return {
        "data": {
            "status": "ok",
            "database": "available",
            "pgvector": "enabled" if has_vector else "missing",
        }
    }
