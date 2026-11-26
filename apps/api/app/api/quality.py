"""Quality dashboard API hooks (Phase 5)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.diagrams.model import DiagramValidationError, validate_diagram_model
from app.diagrams.render import render_diagram
from app.models.user import User
from app.quality.hooks import quality_dashboard_hooks
from app.rbac.deps import require_role
from app.rbac.roles import RoleName

router = APIRouter(prefix="/admin/quality", tags=["admin-quality"])


class DiagramValidateIn(BaseModel):
    diagram: dict = Field(default_factory=dict)


class DiagramValidateOut(BaseModel):
    ok: bool
    engine: str | None = None
    error: str | None = None
    svg_preview: str | None = None


@router.get("/hooks")
def quality_hooks_status(
    _user: User = Depends(require_role(RoleName.TEMPLATE_EDITOR)),
) -> dict:
    """Report Vale/lychee availability and a dry-run against /tmp if present."""
    results = quality_dashboard_hooks(Path("/tmp/docforge-artifacts"))
    return {
        "hooks": results,
        "note": "Hooks run against generated preview.html when present; binaries optional.",
    }


@router.post("/diagrams/validate", response_model=DiagramValidateOut)
def validate_diagram(
    body: DiagramValidateIn,
    _user: User = Depends(require_role(RoleName.TEMPLATE_EDITOR)),
) -> DiagramValidateOut:
    try:
        model = validate_diagram_model(body.diagram)
        rendered = render_diagram(model, None)
        return DiagramValidateOut(ok=True, engine=rendered.engine, svg_preview=rendered.svg)
    except DiagramValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
