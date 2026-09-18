"""Add Paddle customer/subscription columns

Revision ID: 002_paddle
Revises: 001_saas
Create Date: 2026-09-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "002_paddle"
down_revision = "001_saas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("v2_subscriptions", sa.Column("paddle_customer_id", sa.String(), nullable=True))
    op.add_column("v2_subscriptions", sa.Column("paddle_subscription_id", sa.String(), nullable=True))
    op.create_index("ix_v2_subscriptions_paddle_customer_id", "v2_subscriptions", ["paddle_customer_id"])
    op.create_index("ix_v2_subscriptions_paddle_subscription_id", "v2_subscriptions", ["paddle_subscription_id"])


def downgrade() -> None:
    op.drop_index("ix_v2_subscriptions_paddle_subscription_id", table_name="v2_subscriptions")
    op.drop_index("ix_v2_subscriptions_paddle_customer_id", table_name="v2_subscriptions")
    op.drop_column("v2_subscriptions", "paddle_subscription_id")
    op.drop_column("v2_subscriptions", "paddle_customer_id")
