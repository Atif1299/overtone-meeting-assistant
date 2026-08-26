from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import AgentVersion

DEFAULT_INSTRUCTIONS = """You are Overtone, a live meeting presentation agent.
Answer only from tool results (slide_content / searchable deck text).
If the source is thin or missing, say you cannot find it in the deck — do not invent.
Use navigate_to_slide, get_slide_details, and search_and_answer to stay grounded.
Keep answers concise for spoken delivery.
If the user asks you to stop, pause, wait, or hold — stop speaking immediately and wait for the next instruction.
When interrupted mid-answer, do not continue the previous sentence; wait and listen."""


def _workspace_filter(query, workspace_id: str | None):
    if workspace_id:
        return query.filter(
            (AgentVersion.workspace_id == workspace_id) | (AgentVersion.workspace_id.is_(None))
        )
    return query


def list_agents(db: Session, workspace_id: str | None = None) -> list[str]:
    q = db.query(AgentVersion.name)
    q = _workspace_filter(q, workspace_id)
    rows = q.distinct().all()
    names = sorted({r[0] for r in rows})
    return names or ["default"]


def list_versions(db: Session, name: str, workspace_id: str | None = None) -> list[AgentVersion]:
    q = db.query(AgentVersion).filter(AgentVersion.name == name)
    q = _workspace_filter(q, workspace_id)
    return q.order_by(AgentVersion.version.desc()).all()


def get_active(db: Session, name: str = "default", workspace_id: str | None = None) -> AgentVersion | None:
    q = db.query(AgentVersion).filter(AgentVersion.name == name, AgentVersion.is_active.is_(True))
    q = _workspace_filter(q, workspace_id)
    return q.order_by(AgentVersion.version.desc()).first()


def ensure_default_agent(db: Session, workspace_id: str | None = None) -> AgentVersion:
    existing = get_active(db, "default", workspace_id)
    if existing:
        return existing
    row = AgentVersion(
        name="default",
        version=1,
        instructions=DEFAULT_INSTRUCTIONS,
        is_active=True,
        workspace_id=workspace_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def create_version(db: Session, name: str, instructions: str, workspace_id: str | None = None) -> AgentVersion:
    latest = (
        db.query(AgentVersion)
        .filter(AgentVersion.name == name, AgentVersion.workspace_id == workspace_id)
        .order_by(AgentVersion.version.desc())
        .first()
    )
    version = (latest.version + 1) if latest else 1
    row = AgentVersion(
        name=name,
        version=version,
        instructions=instructions,
        is_active=False,
        workspace_id=workspace_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def activate_version(db: Session, name: str, version: int, workspace_id: str | None = None) -> AgentVersion | None:
    rows = list_versions(db, name, workspace_id)
    target = next((r for r in rows if r.version == version), None)
    if not target:
        return None
    for r in rows:
        if r.workspace_id == workspace_id:
            r.is_active = r.version == version
    db.commit()
    db.refresh(target)
    return target


def instructions_for(db: Session, name: str = "default", workspace_id: str | None = None) -> str:
    ensure_default_agent(db, workspace_id)
    active = get_active(db, name, workspace_id) or get_active(db, "default", workspace_id)
    return (active.instructions if active else DEFAULT_INSTRUCTIONS) or DEFAULT_INSTRUCTIONS
