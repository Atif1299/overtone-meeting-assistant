from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.domain import agents as agent_store
from app.http.auth import WorkspaceContext, get_workspace_context

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


def _ws(ctx: WorkspaceContext) -> str | None:
    return None if ctx.is_operator else ctx.workspace_id


@router.get("")
def list_agents(
    db: Session = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    agent_store.ensure_default_agent(db, _ws(ctx))
    return {"agents": agent_store.list_agents(db, _ws(ctx))}


@router.get("/{name}/versions", response_model=list[AgentVersionOut])
def versions(
    name: str,
    db: Session = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    agent_store.ensure_default_agent(db, _ws(ctx))
    rows = agent_store.list_versions(db, name, _ws(ctx))
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
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    row = agent_store.create_version(db, name, body.instructions, _ws(ctx))
    return AgentVersionOut(
        name=row.name, version=row.version, instructions=row.instructions, is_active=row.is_active
    )


@router.post("/{name}/activate", response_model=AgentVersionOut)
def activate(
    name: str,
    body: ActivateIn,
    db: Session = Depends(get_db),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    row = agent_store.activate_version(db, name, body.version, _ws(ctx))
    if not row:
        raise HTTPException(status_code=404, detail="Version not found")
    return AgentVersionOut(
        name=row.name, version=row.version, instructions=row.instructions, is_active=row.is_active
    )
