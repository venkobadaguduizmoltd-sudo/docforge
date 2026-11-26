"""Docs-as-code and drift API endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.integrations.docs_as_code import build_docs_pr_body, open_docs_pull_request
from app.integrations.drift import (
    detect_drift,
    incremental_regen_plan,
    map_changed_files_to_sections,
)
from app.providers.factory import get_repo_provider
from app.rbac.deps import get_current_user

router = APIRouter(prefix="/integrations", tags=["integrations"])


class DocsAsCodeRequest(BaseModel):
    provider: str = "fixture"
    full_name: str
    head_branch: str
    base_branch: str = "main"
    title: str = "docs: DocForge generated documentation"
    body: str | None = None
    template_slug: str = "tech-overview"
    commit_sha: str = ""
    sections: list[str] = Field(default_factory=list)
    comment_body: str | None = "DocForge opened this PR with generated documentation."
    token: str | None = None
    api_base: str | None = None


class DriftRequest(BaseModel):
    provider: str = "fixture"
    full_name: str
    base_ref: str = "main"
    pinned_sha: str
    changed_files: list[str] = Field(default_factory=list)
    all_sections: list[str] = Field(default_factory=list)
    token: str | None = None
    api_base: str | None = None


class MapSectionsRequest(BaseModel):
    changed_files: list[str]


@router.post("/docs-as-code")
async def docs_as_code(body: DocsAsCodeRequest, _user=Depends(get_current_user)) -> dict[str, Any]:
    try:
        provider = get_repo_provider(body.provider, token=body.token, api_base=body.api_base)
        await provider.authenticate()
        pr_body = body.body or build_docs_pr_body(
            template_slug=body.template_slug,
            commit_sha=body.commit_sha or "unknown",
            sections=body.sections or None,
        )
        result = await open_docs_pull_request(
            provider,
            full_name=body.full_name,
            head_branch=body.head_branch,
            base_branch=body.base_branch,
            title=body.title,
            body=pr_body,
            head_sha=body.commit_sha or None,
            comment_body=body.comment_body,
        )
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    pr = result.pull_request
    return {
        "pull_request": {
            "id": pr.id,
            "number": pr.number,
            "url": pr.url,
            "title": pr.title,
            "state": pr.state,
            "head_sha": pr.head_sha,
            "base_ref": pr.base_ref,
        },
        "comment": result.comment,
        "status": result.status,
    }


@router.post("/drift")
async def drift_check(body: DriftRequest, _user=Depends(get_current_user)) -> dict[str, Any]:
    try:
        provider = get_repo_provider(body.provider, token=body.token, api_base=body.api_base)
        await provider.authenticate()
        report = await detect_drift(
            provider=provider,
            full_name=body.full_name,
            base_ref=body.base_ref,
            pinned_sha=body.pinned_sha,
            changed_files=body.changed_files or None,
        )
        plan = incremental_regen_plan(report, all_sections=body.all_sections or None)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"drift": report.to_dict(), "regen_plan": plan}


@router.post("/map-sections")
async def map_sections(body: MapSectionsRequest, _user=Depends(get_current_user)) -> dict:
    return {"sections": map_changed_files_to_sections(body.changed_files)}
