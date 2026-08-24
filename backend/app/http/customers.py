from __future__ import annotations

import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.models import ApiKey
from app.http.auth import require_admin_key

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


class CustomerCreate(BaseModel):
    customer_name: str
    customer_id: str | None = None


class CustomerOut(BaseModel):
    customer_id: str
    customer_name: str
    api_key: str
    is_active: bool


@router.post("", response_model=CustomerOut, dependencies=[Depends(require_admin_key)])
def create_customer(body: CustomerCreate, db: Session = Depends(get_db)):
    cid = body.customer_id or f"cust_{uuid.uuid4().hex[:10]}"
    if db.query(ApiKey).filter(ApiKey.customer_id == cid).first():
        raise HTTPException(status_code=409, detail="customer_id exists")
    key = f"otv2_{secrets.token_urlsafe(24)}"
    row = ApiKey(key=key, customer_id=cid, customer_name=body.customer_name, is_active=True)
    db.add(row)
    db.commit()
    return CustomerOut(
        customer_id=cid, customer_name=body.customer_name, api_key=key, is_active=True
    )


@router.get("", response_model=list[CustomerOut], dependencies=[Depends(require_admin_key)])
def list_customers(db: Session = Depends(get_db)):
    rows = db.query(ApiKey).order_by(ApiKey.created_at.desc()).all()
    return [
        CustomerOut(
            customer_id=r.customer_id,
            customer_name=r.customer_name,
            api_key=r.key,
            is_active=r.is_active,
        )
        for r in rows
    ]


@router.delete("/{customer_id}", dependencies=[Depends(require_admin_key)])
def revoke_customer(customer_id: str, db: Session = Depends(get_db)):
    row = db.query(ApiKey).filter(ApiKey.customer_id == customer_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    row.is_active = False
    db.commit()
    return {"ok": True}
