from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from pydantic import BaseModel, Field


DEFAULT_AGENT_NAME = "default"
DEFAULT_SYSTEM_PROMPT = (
    "You are Overtone, a live AI presenter — quick-thinking, warm, and genuinely engaging. "
    "You read the room. You make people feel heard before you make them think.\n\n"

    "GROUNDING LAW — ABSOLUTE, NON-NEGOTIABLE:\n"
    "• Your spoken answers MUST be derived EXCLUSIVELY from the results returned by tools (slide_content, rich_metadata, or external_data).\n"
    "• STRICTLY FORBIDDEN from adding facts from training data or making up examples.\n"
    "• If information is not clearly in the deck, use fetch_external_data to find it. Do not guess.\n\n"

    "VOICE AND STYLE:\n"
    "• Confident, knowledgeable presenter — not a robot reading a script.\n"
    "• Natural spoken language: short sentences, active voice, 2-3 sentences per turn.\n"
    "• Transitions between slides should sound natural and varied.\n"
    "• NEVER start with 'Certainly!', 'Great question!', or 'Sure!'.\n"
    "• NEVER say 'As an AI'. Silence beats filler while tools run.\n\n"

    "TOOL USAGE RULES:\n"
    "• navigate_to_slide: Use for movement and pacing. **Rule**: ALWAYS ask permission before jumping to a different slide while answering questions.\n"
    "• search_and_answer: Use for ANY content question about topics or details in the deck.\n"
    "• get_slide_details: Use to fetch raw visual and data details for a specific page. **Rule**: Use this for ANY question about 'this' or 'the current' slide to ensure precision.\n"
    "• fetch_external_data: Use to fetch data NOT on the slides. **Rule**: Use this for any external queries, current events, or data missing from the deck.\n"
    "• leave_call: Use for goodbyes and exit signals ('bye', 'that's all', etc.).\n"
    "• Always call a tool BEFORE speaking from its result.\n\n"

    "INTERACTION:\n"
    "• Clear questions — act immediately.\n"
    "• Ambiguous questions — confirm once, quickly.\n"
    "• End every response with a natural check-in or forward pull.\n"
)


class AgentVersion(BaseModel):
    agent_name: str
    version_number: int
    system_prompt: str
    presentation_id: str | None = None
    is_active: bool
    created_at: datetime


class AgentSummary(BaseModel):
    agent_name: str
    active_version: int | None = None
    active_presentation_id: str | None = None
    updated_at: datetime
    version_count: int = 0
    prompt_preview: str = Field(default="")


class AgentStore:
    def __init__(self) -> None:
        self._db_path = Path("./data/agents.db")
        self._lock = Lock()
        self._initialized = False

    def configure(self, db_path: str) -> None:
        self._db_path = Path(db_path or "./data/agents.db")

    def initialize(self) -> None:
        with self._lock:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS agent_versions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        agent_name TEXT NOT NULL,
                        version_number INTEGER NOT NULL,
                        system_prompt TEXT NOT NULL,
                        presentation_id TEXT,
                        is_active INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL,
                        UNIQUE(agent_name, version_number)
                    )
                    """
                )
                cols = {
                    str(row["name"])
                    for row in conn.execute("PRAGMA table_info(agent_versions)").fetchall()
                }
                if "presentation_id" not in cols:
                    conn.execute(
                        "ALTER TABLE agent_versions ADD COLUMN presentation_id TEXT"
                    )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_agent_versions_agent_name "
                    "ON agent_versions(agent_name)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_agent_versions_active "
                    "ON agent_versions(agent_name, is_active)"
                )
                conn.commit()
            self._initialized = True
        self.ensure_agent(
            agent_name=DEFAULT_AGENT_NAME,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            activate=True,
        )

    def list_agents(self) -> list[AgentSummary]:
        self._ensure_initialized()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    a.agent_name AS agent_name,
                    (
                        SELECT version_number
                        FROM agent_versions av
                        WHERE av.agent_name = a.agent_name AND av.is_active = 1
                        LIMIT 1
                    ) AS active_version,
                    MAX(a.created_at) AS updated_at,
                    COUNT(*) AS version_count,
                    (
                        SELECT system_prompt
                        FROM agent_versions av2
                        WHERE av2.agent_name = a.agent_name AND av2.is_active = 1
                        LIMIT 1
                    ) AS active_prompt,
                    (
                        SELECT presentation_id
                        FROM agent_versions av3
                        WHERE av3.agent_name = a.agent_name AND av3.is_active = 1
                        LIMIT 1
                    ) AS active_presentation_id
                FROM agent_versions a
                GROUP BY a.agent_name
                ORDER BY a.agent_name ASC
                """
            ).fetchall()
        return [
            AgentSummary(
                agent_name=str(row["agent_name"]),
                active_version=int(row["active_version"]) if row["active_version"] is not None else None,
                active_presentation_id=row["active_presentation_id"],
                updated_at=_parse_dt(str(row["updated_at"])),
                version_count=int(row["version_count"]),
                prompt_preview=_preview(str(row["active_prompt"] or "")),
            )
            for row in rows
        ]

    def list_versions(self, agent_name: str) -> list[AgentVersion]:
        self._ensure_initialized()
        agent_name = _normalize_agent_name(agent_name)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT agent_name, version_number, system_prompt, presentation_id, is_active, created_at
                FROM agent_versions
                WHERE agent_name = ?
                ORDER BY version_number DESC
                """,
                (agent_name,),
            ).fetchall()
        return [self._row_to_version(row) for row in rows]

    def get_active_version(self, agent_name: str) -> AgentVersion | None:
        self._ensure_initialized()
        agent_name = _normalize_agent_name(agent_name)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT agent_name, version_number, system_prompt, presentation_id, is_active, created_at
                FROM agent_versions
                WHERE agent_name = ? AND is_active = 1
                LIMIT 1
                """,
                (agent_name,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_version(row)

    def ensure_agent(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        presentation_id: str | None = None,
        activate: bool = True,
    ) -> AgentVersion:
        existing = self.get_active_version(agent_name)
        if existing:
            return existing
        return self.create_version(
            agent_name=agent_name,
            system_prompt=system_prompt,
            presentation_id=presentation_id,
            activate=activate,
        )

    def create_version(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        presentation_id: str | None = None,
        activate: bool = True,
    ) -> AgentVersion:
        self._ensure_initialized()
        agent_name = _normalize_agent_name(agent_name)
        prompt = _normalize_prompt(system_prompt)
        selected_presentation = _normalize_presentation_id(presentation_id)
        created_at = _now_iso()
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT COALESCE(MAX(version_number), 0) AS max_version "
                    "FROM agent_versions WHERE agent_name = ?",
                    (agent_name,),
                ).fetchone()
                next_version = int(row["max_version"]) + 1
                if activate:
                    conn.execute(
                        "UPDATE agent_versions SET is_active = 0 WHERE agent_name = ?",
                        (agent_name,),
                    )
                conn.execute(
                    """
                    INSERT INTO agent_versions (
                        agent_name, version_number, system_prompt, presentation_id, is_active, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        agent_name,
                        next_version,
                        prompt,
                        selected_presentation,
                        1 if activate else 0,
                        created_at,
                    ),
                )
                conn.commit()
        active = self.get_active_version(agent_name) if activate else None
        if active:
            return active
        versions = self.list_versions(agent_name)
        return versions[0]

    def activate_version(self, *, agent_name: str, version_number: int) -> AgentVersion:
        self._ensure_initialized()
        agent_name = _normalize_agent_name(agent_name)
        target = int(version_number)
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT 1 FROM agent_versions WHERE agent_name = ? AND version_number = ?",
                    (agent_name, target),
                ).fetchone()
                if not row:
                    raise ValueError(f"Version {target} not found for agent '{agent_name}'")
                conn.execute(
                    "UPDATE agent_versions SET is_active = 0 WHERE agent_name = ?",
                    (agent_name,),
                )
                conn.execute(
                    "UPDATE agent_versions SET is_active = 1 WHERE agent_name = ? AND version_number = ?",
                    (agent_name, target),
                )
                conn.commit()
        active = self.get_active_version(agent_name)
        if not active:
            raise ValueError(f"Could not activate version {target} for agent '{agent_name}'")
        return active

    def _row_to_version(self, row: sqlite3.Row) -> AgentVersion:
        return AgentVersion(
            agent_name=str(row["agent_name"]),
            version_number=int(row["version_number"]),
            system_prompt=str(row["system_prompt"]),
            presentation_id=row["presentation_id"],
            is_active=bool(int(row["is_active"])),
            created_at=_parse_dt(str(row["created_at"])),
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        self.initialize()

    def reset_for_tests(self) -> None:
        self._ensure_initialized()
        with self._lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM agent_versions")
                conn.commit()
        self.ensure_agent(
            agent_name=DEFAULT_AGENT_NAME,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            activate=True,
        )


def _normalize_agent_name(agent_name: str) -> str:
    value = (agent_name or "").strip()
    if not value:
        raise ValueError("agent_name is required")
    if len(value) > 80:
        raise ValueError("agent_name must be 80 characters or fewer")
    return value


def _normalize_prompt(prompt: str) -> str:
    value = (prompt or "").strip()
    if not value:
        raise ValueError("system_prompt is required")
    return value


def _normalize_presentation_id(presentation_id: str | None) -> str | None:
    if presentation_id is None:
        return None
    value = str(presentation_id).strip()
    return value or None


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _preview(text: str, limit: int = 120) -> str:
    clean = " ".join((text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1] + "…"


agent_store = AgentStore()
