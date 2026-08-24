from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
DATABASE_URL = settings.database_url or "sqlite:///./overtone_v2.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    if "postgres" in DATABASE_URL.lower():
        from app.indexing.vector_store import ensure_chunks_table_safe

        ensure_chunks_table_safe()


def is_postgres() -> bool:
    return "postgres" in DATABASE_URL.lower()


def exec_sql(sql: str, params: dict | None = None):
    with engine.begin() as conn:
        return conn.execute(text(sql), params or {})
