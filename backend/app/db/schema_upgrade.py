from __future__ import annotations

from sqlalchemy import inspect, text

from app.db import engine, is_postgres


def ensure_schema_upgrades() -> None:
    """Add SaaS columns/tables to existing deployments without Alembic CLI."""
    insp = inspect(engine)
    tables = set(insp.get_table_names())

    if "v2_agents" in tables:
        cols = {c["name"] for c in insp.get_columns("v2_agents")}
        if "workspace_id" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE v2_agents ADD COLUMN workspace_id VARCHAR"))
                try:
                    conn.execute(text("CREATE INDEX ix_v2_agents_workspace_id ON v2_agents (workspace_id)"))
                except Exception:  # noqa: BLE001
                    pass

    # create_all handles new SaaS tables; this covers legacy DBs
