"""Phase 2: section locks, citations, suggestions, document provenance.

Revision ID: 0003_phase2_corrections
Revises: 0002_phase1_repo_fields
Create Date: 2026-11-25

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_phase2_corrections"
down_revision: Union[str, None] = "0002_phase1_repo_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("source_job_id", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("template_slug", sa.String(length=128), nullable=True))
    op.add_column("documents", sa.Column("template_sha256", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("pinned_commit_sha", sa.String(length=64), nullable=True))

    op.add_column(
        "document_sections",
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "document_sections",
        sa.Column(
            "citations_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "document_sections",
        sa.Column("pending_suggestion_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document_sections", "pending_suggestion_json")
    op.drop_column("document_sections", "citations_json")
    op.drop_column("document_sections", "is_locked")
    op.drop_column("documents", "pinned_commit_sha")
    op.drop_column("documents", "template_sha256")
    op.drop_column("documents", "template_slug")
    op.drop_column("documents", "source_job_id")
