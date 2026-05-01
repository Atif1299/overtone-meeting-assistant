from __future__ import annotations

import secrets
import string
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.auth import require_admin_key
from database import get_db
from models.api_key import ApiKey
from models.bot_session import BotSession
from services import storage as storage_mod
import shutil

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin_key)])

class CreateCustomerRequest(BaseModel):
    customer_name: str

class CustomerResponse(BaseModel):
    customer_id: str
    customer_name: str
    api_key: str
    is_active: bool
    created_at: str

@router.post("/customer", response_model=CustomerResponse)
async def create_customer(
    request: CreateCustomerRequest,
    db: Session = Depends(get_db)
):
    """
    Create a new customer and generate an API key.
    """
    customer_id = str(uuid.uuid4())
    # Generate a random API key (e.g., cust_...)
    raw_key = "cust_" + "".join(secrets.choice(string.ascii_letters + string.digits) for i in range(32))
    
    api_key = ApiKey(
        key=raw_key,
        customer_id=customer_id,
        customer_name=request.customer_name,
        is_active=True
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    
    return CustomerResponse(
        customer_id=api_key.customer_id,
        customer_name=api_key.customer_name,
        api_key=api_key.key,
        is_active=api_key.is_active,
        created_at=api_key.created_at.isoformat()
    )

@router.get("/customer", response_model=List[CustomerResponse])
async def list_customers(
    db: Session = Depends(get_db)
):
    """List all customers and their API keys."""
    keys = db.query(ApiKey).all()
    return [
        CustomerResponse(
            customer_id=k.customer_id,
            customer_name=k.customer_name,
            api_key=k.key,
            is_active=k.is_active,
            created_at=k.created_at.isoformat()
        )
        for k in keys
    ]

@router.get("/customer/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific customer by ID."""
    api_key = db.query(ApiKey).filter(ApiKey.customer_id == customer_id).first()
    if not api_key:
        raise HTTPException(status_code=404, detail="Customer not found")
        
    return CustomerResponse(
        customer_id=api_key.customer_id,
        customer_name=api_key.customer_name,
        api_key=api_key.key,
        is_active=api_key.is_active,
        created_at=api_key.created_at.isoformat()
    )


@router.delete("/customer/{customer_id}")
async def delete_customer(
    customer_id: str,
    db: Session = Depends(get_db),
):
    """Delete a customer, their API keys, and associated bot sessions/presentations."""
    api_keys = db.query(ApiKey).filter(ApiKey.customer_id == customer_id).all()
    if not api_keys:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Delete bot sessions and associated presentation files where possible
    bots = db.query(BotSession).filter(BotSession.customer_id == customer_id).all()
    bots_deleted = 0
    for b in bots:
        pid = b.presentation_id
        if pid:
            try:
                d = storage_mod.presentation_dir(pid)
                if d and d.exists():
                    shutil.rmtree(d)
            except Exception:
                # ignore errors during storage cleanup
                pass
        try:
            db.delete(b)
            bots_deleted += 1
        except Exception:
            pass

    keys_deleted = 0
    for k in api_keys:
        try:
            db.delete(k)
            keys_deleted += 1
        except Exception:
            pass

    db.commit()

    return {"customer_id": customer_id, "deleted": True, "bots_deleted": bots_deleted, "keys_deleted": keys_deleted}
