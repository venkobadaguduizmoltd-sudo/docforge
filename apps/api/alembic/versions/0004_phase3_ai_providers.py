"""Phase 3: ai_providers and provider_policies tables.

Revision ID: 0004_phase3_ai_providers
Revises: 0003_phase2_corrections
Create Date: 2026-11-25

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_phase3_ai_providers"
down_revision: Union[str, None] = "0003_phase2_corrections"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("adapter_type", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="model"),
        sa.Column("base_url", sa.String(length=512), nullable=True),
        sa.Column("default_model", sa.String(length=255), nullable=True),
        sa.Column(
            "config_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("encrypted_api_key", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_ai_providers_adapter_type", "ai_providers", ["adapter_type"])

    op.create_table(
        "provider_policies",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("primary_provider_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "fallback_provider_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("budget_daily_tokens", sa.Integer(), nullable=True),
        sa.Column("budget_monthly_tokens", sa.Integer(), nullable=True),
        sa.Column("tokens_used_today", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_used_month", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("allow_paid_providers", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["primary_provider_id"],
            ["ai_providers.id"],
            ondelete="SET NULL",
        ),
    )


def downgrade() -> None:
    op.drop_table("provider_policies")
    op.drop_index("ix_ai_providers_adapter_type", table_name="ai_providers")
    op.drop_table("ai_providers")
