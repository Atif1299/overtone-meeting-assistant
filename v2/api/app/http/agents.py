from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.models import ApiKey
from app.domain import agents as agent_store
from app.http.auth import require_api_key

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


class AgentVersionOut(BaseModel):
    name: str
    version: int
    instructions: str
    is_active: bool


class CreateVersionIn(BaseModel):
    instructions: str


class ActivateIn(BaseModel):
    version: int


@router.get("")
def list_agents(db: Session = Depends(get_db), api_key: ApiKey = Depends(require_api_key)):
    agent_store.ensure_default_agent(db)
    return {"agents": agent_store.list_agents(db)}


@router.get("/{name}/versions", response_model=list[AgentVersionOut])
def versions(name: str, db: Session = Depends(get_db), api_key: ApiKey = Depends(require_api_key)):
    agent_store.ensure_default_agent(db)
    rows = agent_store.list_versions(db, name)
    return [
        AgentVersionOut(
            name=r.name, version=r.version, instructions=r.instructions, is_active=r.is_active
        )
        for r in rows
    ]


@router.post("/{name}/versions", response_model=AgentVersionOut)
def create_version(
    name: str,
    body: CreateVersionIn,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(require_api_key),
):
    row = agent_store.create_version(db, name, body.instructions)
    return AgentVersionOut(
        name=row.name, version=row.version, instructions=row.instructions, is_active=row.is_active
    )


@router.post("/{name}/activate", response_model=AgentVersionOut)
def activate(
    name: str,
    body: ActivateIn,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(require_api_key),
):
    row = agent_store.activate_version(db, name, body.version)
    if not row:
        raise HTTPException(status_code=404, detail="Version not found")
    return AgentVersionOut(
        name=row.name, version=row.version, instructions=row.instructions, is_active=row.is_active
    )
