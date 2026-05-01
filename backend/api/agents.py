from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import require_customer_key
from services.agent_store import AgentSummary, AgentVersion, agent_store

router = APIRouter(prefix="/api/agents", tags=["agents"], dependencies=[Depends(require_customer_key)])


class CreateVersionRequest(BaseModel):
    system_prompt: str = Field(..., min_length=1)
    presentation_id: str | None = None
    activate: bool = True


class ActivateVersionRequest(BaseModel):
    version_number: int = Field(..., ge=1)


@router.get("", response_model=list[AgentSummary])
async def list_agents() -> list[AgentSummary]:
    return agent_store.list_agents()


@router.get("/{agent_name}/versions", response_model=list[AgentVersion])
async def list_agent_versions(agent_name: str) -> list[AgentVersion]:
    try:
        versions = agent_store.list_versions(agent_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not versions:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    return versions


@router.post("/{agent_name}/versions", response_model=AgentVersion)
async def create_agent_version(agent_name: str, body: CreateVersionRequest) -> AgentVersion:
    if body.presentation_id:
        from services import storage as storage_mod

        if not storage_mod.get_presentation(body.presentation_id):
            raise HTTPException(
                status_code=404,
                detail=f"Presentation '{body.presentation_id}' not found",
            )
    try:
        return agent_store.create_version(
            agent_name=agent_name,
            system_prompt=body.system_prompt,
            presentation_id=body.presentation_id,
            activate=body.activate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{agent_name}/activate", response_model=AgentVersion)
async def activate_agent_version(agent_name: str, body: ActivateVersionRequest) -> AgentVersion:
    try:
        return agent_store.activate_version(
            agent_name=agent_name,
            version_number=body.version_number,
        )
    except ValueError as exc:
        message = str(exc)
        status = 404 if "not found" in message else 400
        raise HTTPException(status_code=status, detail=message) from exc
