from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Boolean
from database import Base

def _utcnow():
    return datetime.now(timezone.utc)

class ApiKey(Base):
    __tablename__ = "api_keys"

    key = Column(String, primary_key=True, index=True)
    customer_id = Column(String, unique=True, index=True)
    customer_name = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)
