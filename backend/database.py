from __future__ import annotations

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from config import get_settings

settings = get_settings()

# Use SQLite for local development, PostgreSQL for production
if settings.database_url:
    DATABASE_URL = settings.database_url
else:
    DATABASE_URL = "sqlite:///./overtone.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    from models.bot_session import BotSession  # noqa
    from models.api_key import ApiKey  # noqa
    Base.metadata.create_all(bind=engine)