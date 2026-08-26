"""SaaS multi-tenant tables

Revision ID: 001_saas
Revises:
Create Date: 2026-08-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "001_saas"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "v2_users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_v2_users_email", "v2_users", ["email"], unique=True)

    op.create_table(
        "v2_workspaces",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), server_default=""),
        sa.Column("owner_user_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_v2_workspaces_owner_user_id", "v2_workspaces", ["owner_user_id"])

    op.create_table(
        "v2_workspace_members",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(), server_default="owner"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_v2_workspace_members_workspace_id", "v2_workspace_members", ["workspace_id"])
    op.create_index("ix_v2_workspace_members_user_id", "v2_workspace_members", ["user_id"])

    op.create_table(
        "v2_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("plan", sa.String(), server_default="free"),
        sa.Column("status", sa.String(), server_default="active"),
        sa.Column("stripe_customer_id", sa.String(), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(), nullable=True),
        sa.Column("current_period_start", sa.DateTime(), nullable=True),
        sa.Column("current_period_end", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_v2_subscriptions_workspace_id", "v2_subscriptions", ["workspace_id"])

    op.create_table(
        "v2_usage_counters",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("metric", sa.String(), nullable=False),
        sa.Column("period_month", sa.String(), nullable=False),
        sa.Column("count", sa.Integer(), server_default="0"),
    )
    op.create_index("ix_v2_usage_counters_workspace_id", "v2_usage_counters", ["workspace_id"])

    with op.batch_alter_table("v2_agents") as batch:
        batch.add_column(sa.Column("workspace_id", sa.String(), nullable=True))
        batch.create_index("ix_v2_agents_workspace_id", ["workspace_id"])


def downgrade() -> None:
    with op.batch_alter_table("v2_agents") as batch:
        batch.drop_index("ix_v2_agents_workspace_id")
        batch.drop_column("workspace_id")
    op.drop_table("v2_usage_counters")
    op.drop_table("v2_subscriptions")
    op.drop_table("v2_workspace_members")
    op.drop_table("v2_workspaces")
    op.drop_table("v2_users")
