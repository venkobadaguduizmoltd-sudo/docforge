"""Phase 4 — template studio status, tags, version metadata.

Revision ID: 0005_phase4_template_studio
Revises: 0004_phase3_ai_providers
Create Date: 2026-11-26
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_phase4_template_studio"
down_revision: Union[str, None] = "0004_phase3_ai_providers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "templates",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
    )
    op.add_column(
        "templates",
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "templates",
        sa.Column("source", sa.String(length=32), nullable=False, server_default="studio"),
    )
    op.add_column(
        "template_versions",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
    )
    op.add_column("template_versions", sa.Column("changelog", sa.Text(), nullable=True))
    op.add_column(
        "template_versions",
        sa.Column(
            "assets_meta",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "template_versions",
        sa.Column("last_test_run_ok", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("template_versions", "last_test_run_ok")
    op.drop_column("template_versions", "assets_meta")
    op.drop_column("template_versions", "changelog")
    op.drop_column("template_versions", "status")
    op.drop_column("templates", "source")
    op.drop_column("templates", "tags")
    op.drop_column("templates", "status")
