"""Repository provider endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from app.providers.factory import get_repo_provider
from app.rbac.deps import get_current_user
from app.schemas.jobs import ListRefsRequest, ListReposRequest

router = APIRouter(prefix="/repos", tags=["repos"])


@router.post("/list")
async def list_repos(body: ListReposRequest, _user=Depends(get_current_user)) -> dict:
    try:
        provider = get_repo_provider(body.provider, token=body.token, api_base=body.api_base)
        await provider.authenticate()
        repos = await provider.list_repos(body.query)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "provider": body.provider,
        "repos": [
            {
                "id": r.id,
                "full_name": r.full_name,
                "clone_url": r.clone_url,
                "default_branch": r.default_branch,
                "private": r.private,
            }
            for r in repos
        ],
    }


@router.post("/refs")
async def list_refs(body: ListRefsRequest, _user=Depends(get_current_user)) -> dict:
    try:
        provider = get_repo_provider(body.provider, token=body.token, api_base=body.api_base)
        await provider.authenticate()
        refs = await provider.list_refs(body.full_name)
        pinned = await provider.resolve_ref(body.full_name, refs[0].name if refs else "main")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "provider": body.provider,
        "full_name": body.full_name,
        "refs": [{"name": r.name, "sha": r.sha, "ref_type": r.ref_type} for r in refs],
        "example_resolved_sha": pinned,
    }
