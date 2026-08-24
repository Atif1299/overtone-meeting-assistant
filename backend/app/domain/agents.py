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


def list_agents(db: Session) -> list[str]:
    rows = db.query(AgentVersion.name).distinct().all()
    names = sorted({r[0] for r in rows})
    return names or ["default"]


def list_versions(db: Session, name: str) -> list[AgentVersion]:
    return (
        db.query(AgentVersion)
        .filter(AgentVersion.name == name)
        .order_by(AgentVersion.version.desc())
        .all()
    )


def get_active(db: Session, name: str = "default") -> AgentVersion | None:
    return (
        db.query(AgentVersion)
        .filter(AgentVersion.name == name, AgentVersion.is_active.is_(True))
        .order_by(AgentVersion.version.desc())
        .first()
    )


def ensure_default_agent(db: Session) -> AgentVersion:
    existing = get_active(db, "default")
    if existing:
        return existing
    row = AgentVersion(name="default", version=1, instructions=DEFAULT_INSTRUCTIONS, is_active=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def create_version(db: Session, name: str, instructions: str) -> AgentVersion:
    latest = (
        db.query(AgentVersion)
        .filter(AgentVersion.name == name)
        .order_by(AgentVersion.version.desc())
        .first()
    )
    version = (latest.version + 1) if latest else 1
    row = AgentVersion(name=name, version=version, instructions=instructions, is_active=False)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def activate_version(db: Session, name: str, version: int) -> AgentVersion | None:
    rows = list_versions(db, name)
    target = next((r for r in rows if r.version == version), None)
    if not target:
        return None
    for r in rows:
        r.is_active = r.version == version
    db.commit()
    db.refresh(target)
    return target


def instructions_for(db: Session, name: str = "default") -> str:
    ensure_default_agent(db)
    active = get_active(db, name) or get_active(db, "default")
    return (active.instructions if active else DEFAULT_INSTRUCTIONS) or DEFAULT_INSTRUCTIONS
