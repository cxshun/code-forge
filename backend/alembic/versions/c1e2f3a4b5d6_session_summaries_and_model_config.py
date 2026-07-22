"""session_summaries table + workspaces.model_config

Revision ID: c1e2f3a4b5d6
Revises: a1b2c3d4e5f6
Create Date: 2026-07-22 10:00:00.000000

P3 context-eng:
- D-CE.1: session_summaries table (1:1 with sessions, CASCADE)
- D-CE.6: workspaces.model_config JSONB column (per-WS model switching)
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c1e2f3a4b5d6"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # D-CE.1: session_summaries 表
    op.create_table(
        "session_summaries",
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("summary_model", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("session_id"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
    )

    # D-CE.6: workspaces.model_config JSONB 列
    op.add_column(
        "workspaces",
        sa.Column("model_config", sa.dialects.postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workspaces", "model_config")
    op.drop_table("session_summaries")
