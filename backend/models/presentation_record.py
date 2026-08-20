from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class PresentationRecord(Base):
    __tablename__ = "presentations"

    presentation_id = Column(String, primary_key=True)
    filename = Column(String, nullable=False)
    status = Column(String, nullable=False, default="uploaded")
    total_pages = Column(Integer, nullable=True)
    indexed_pages = Column(Integer, nullable=False, default=0)
    document_id = Column(String, nullable=True)
    azure_indexed_chunks = Column(Integer, nullable=True)
    metadata_provider = Column(String, nullable=True)
    metadata_model = Column(String, nullable=True)
    index_error = Column(Text, nullable=True)
    extra_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
