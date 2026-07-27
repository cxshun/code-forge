"""drop spans.parent_span_id self-referencing FK

Revision ID: d2f3a4b5c6d7
Revises: c1e2f3a4b5d6
Create Date: 2026-07-27 02:00:00.000000

Child spans are buffered before parents (async CM exits inside-out),
causing FK violations on every batch. Drop the self-referencing FK —
parent_span_id stays as a plain indexed column (standard practice in
tracing systems like Jaeger/OTel).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "d2f3a4b5c6d7"
down_revision: str | None = "c1e2f3a4b5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("fk_spans_parent_span_id_spans", "spans", type_="foreignkey")


def downgrade() -> None:
    op.create_foreign_key(
        "fk_spans_parent_span_id_spans",
        "spans",
        "spans",
        ["parent_span_id"],
        ["span_id"],
        ondelete="CASCADE",
    )
