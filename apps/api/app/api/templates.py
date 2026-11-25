"""Builtin template endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import get_settings
from app.rbac.deps import get_current_user
from app.services.templates import load_builtin_template

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("/builtin/{slug}")
def get_builtin_template(slug: str, _user=Depends(get_current_user)) -> dict:
    settings = get_settings()
    try:
        loaded = load_builtin_template(slug, settings.resolved_templates_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "slug": loaded["slug"],
        "sha256": loaded["sha256"],
        "immutable": True,
        "spec": loaded["spec"],
    }


@router.get("/builtin")
def list_builtin_templates(_user=Depends(get_current_user)) -> dict:
    settings = get_settings()
    root = settings.resolved_templates_root / "builtin"
    items = []
    if root.exists():
        for path in sorted(root.iterdir()):
            if (path / "template.json").exists():
                loaded = load_builtin_template(path.name, settings.resolved_templates_root)
                items.append(
                    {
                        "slug": loaded["slug"],
                        "name": loaded["spec"].get("name"),
                        "sha256": loaded["sha256"],
                        "immutable": True,
                    }
                )
    return {"templates": items}
