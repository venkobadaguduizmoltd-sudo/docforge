"""Add provider fields to repositories for Phase 1.

Revision ID: 0002_phase1_repo_fields
Revises: 0001_baseline
Create Date: 2026-11-25

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_phase1_repo_fields"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("repositories", sa.Column("provider", sa.String(length=64), nullable=True))
    op.add_column("repositories", sa.Column("full_name", sa.String(length=512), nullable=True))
    op.add_column("repositories", sa.Column("pinned_sha", sa.String(length=64), nullable=True))
    op.add_column("jobs", sa.Column("commit_sha", sa.String(length=64), nullable=True))
    op.add_column("jobs", sa.Column("progress_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "progress_json")
    op.drop_column("jobs", "commit_sha")
    op.drop_column("repositories", "pinned_sha")
    op.drop_column("repositories", "full_name")
    op.drop_column("repositories", "provider")
