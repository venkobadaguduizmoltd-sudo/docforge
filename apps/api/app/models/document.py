"""Documents, section content stubs, and revisions."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("teams.id"))
    repository_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id")
    )
    template_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("template_versions.id")
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="draft")
    # Phase 2 provenance
    source_job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    template_slug: Mapped[str | None] = mapped_column(String(128), nullable=True)
    template_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pinned_commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DocumentSection(Base):
    """Content JSON keyed by section_id only — never mutates template structure."""

    __tablename__ = "document_sections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    section_id: Mapped[str] = mapped_column(String(128), nullable=False)
    content_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    citations_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    pending_suggestion_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DocumentRevision(Base):
    __tablename__ = "document_revisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
