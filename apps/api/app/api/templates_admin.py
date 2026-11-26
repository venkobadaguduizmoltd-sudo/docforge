"""Admin template studio endpoints (Phase 4)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.models.user import User
from app.pipeline.generate import new_job_id, run_generate_document
from app.pipeline.job_store import JobRecord, save_job
from app.rbac.deps import require_role
from app.rbac.roles import RoleName
from app.schemas.templates_admin import (
    CloneTemplateRequest,
    PromptTemplateRequest,
    TemplateCreate,
    TemplateListOut,
    TemplateOut,
    TemplateSpecPut,
    TemplateUpdate,
    TemplateYamlPut,
    TestRunOut,
    TestRunRequest,
    YamlOut,
)
from app.template_studio.docx_import import draft_spec_from_docx
from app.template_studio.prompt import draft_spec_from_prompt
from app.template_studio.store import (
    TemplateStatus,
    clone_template,
    create_template,
    deprecate_template,
    ensure_seeded_builtins,
    get_template,
    list_templates,
    mark_test_run,
    publish_template,
    replace_draft_spec,
    update_metadata,
)
from app.template_studio.yaml_codec import spec_from_yaml, spec_to_yaml

router = APIRouter(prefix="/admin/templates", tags=["admin-templates"])


def _out(record, *, include_spec: bool = False) -> TemplateOut:
    return TemplateOut.model_validate(record.public_dict(include_spec=include_spec))


@router.get("", response_model=TemplateListOut)
def admin_list_templates(
    tag: str | None = None,
    status_filter: TemplateStatus | None = Query(default=None, alias="status"),
    _user: User = Depends(require_role(RoleName.TEMPLATE_EDITOR)),
) -> TemplateListOut:
    ensure_seeded_builtins()
    items = list_templates(tag=tag, status=status_filter)
    return TemplateListOut(templates=[_out(t) for t in items])


@router.post("", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
def admin_create_template(
    body: TemplateCreate,
    _user: User = Depends(require_role(RoleName.TEMPLATE_EDITOR)),
) -> TemplateOut:
    try:
        record = create_template(
            name=body.name,
            slug=body.slug,
            description=body.description,
            tags=body.tags,
            spec=body.spec,
            source="studio",
            status="draft",
        )
    except KeyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:  # validation
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _out(record, include_spec=True)


@router.post("/prompt", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
def admin_prompt_template(
    body: PromptTemplateRequest,
    _user: User = Depends(require_role(RoleName.TEMPLATE_EDITOR)),
) -> TemplateOut:
    try:
        spec = draft_spec_from_prompt(body.description, name=body.name)
        record = create_template(
            name=spec["name"],
            slug=spec["slug"],
            description=spec.get("description"),
            tags=list(spec.get("tags") or []),
            spec=spec,
            source="prompt",
            status="draft",
        )
    except KeyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _out(record, include_spec=True)


@router.post("/import-docx", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
async def admin_import_docx(
    file: UploadFile = File(...),
    name: str | None = None,
    _user: User = Depends(require_role(RoleName.TEMPLATE_EDITOR)),
) -> TemplateOut:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        spec = draft_spec_from_docx(data, name=name)
        record = create_template(
            name=spec["name"],
            slug=spec["slug"],
            description=spec.get("description"),
            tags=list(spec.get("tags") or []),
            spec=spec,
            source="docx",
            status="draft",
        )
    except KeyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _out(record, include_spec=True)


@router.get("/{template_id}", response_model=TemplateOut)
def admin_get_template(
    template_id: str,
    _user: User = Depends(require_role(RoleName.TEMPLATE_EDITOR)),
) -> TemplateOut:
    ensure_seeded_builtins()
    record = get_template(template_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return _out(record, include_spec=True)


@router.patch("/{template_id}", response_model=TemplateOut)
def admin_patch_template(
    template_id: str,
    body: TemplateUpdate,
    _user: User = Depends(require_role(RoleName.TEMPLATE_EDITOR)),
) -> TemplateOut:
    record = get_template(template_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Template not found")
    fields = body.model_dump(exclude_unset=True)
    try:
        record = update_metadata(template_id, **fields)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _out(record, include_spec=True)


@router.post("/{template_id}/clone", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
def admin_clone_template(
    template_id: str,
    body: CloneTemplateRequest | None = None,
    _user: User = Depends(require_role(RoleName.TEMPLATE_EDITOR)),
) -> TemplateOut:
    if get_template(template_id) is None:
        raise HTTPException(status_code=404, detail="Template not found")
    try:
        record = clone_template(template_id, new_name=(body.name if body else None))
    except KeyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _out(record, include_spec=True)


@router.put("/{template_id}/spec", response_model=TemplateOut)
def admin_put_spec(
    template_id: str,
    body: TemplateSpecPut,
    _user: User = Depends(require_role(RoleName.TEMPLATE_EDITOR)),
) -> TemplateOut:
    if get_template(template_id) is None:
        raise HTTPException(status_code=404, detail="Template not found")
    try:
        record = replace_draft_spec(template_id, body.spec)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _out(record, include_spec=True)


@router.post("/{template_id}/spec/yaml", response_model=TemplateOut)
def admin_put_spec_yaml(
    template_id: str,
    body: TemplateYamlPut,
    _user: User = Depends(require_role(RoleName.TEMPLATE_EDITOR)),
) -> TemplateOut:
    if get_template(template_id) is None:
        raise HTTPException(status_code=404, detail="Template not found")
    try:
        spec = spec_from_yaml(body.yaml_text)
        record = replace_draft_spec(template_id, spec)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _out(record, include_spec=True)


@router.get("/{template_id}/spec/yaml", response_model=YamlOut)
def admin_get_spec_yaml(
    template_id: str,
    _user: User = Depends(require_role(RoleName.TEMPLATE_EDITOR)),
) -> YamlOut:
    record = get_template(template_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Template not found")
    current = record.current_version()
    if current is None:
        raise HTTPException(status_code=404, detail="No version")
    return YamlOut(yaml_text=spec_to_yaml(current.spec_json))


@router.post("/{template_id}/publish", response_model=TemplateOut)
def admin_publish_template(
    template_id: str,
    _user: User = Depends(require_role(RoleName.TEMPLATE_EDITOR)),
) -> TemplateOut:
    if get_template(template_id) is None:
        raise HTTPException(status_code=404, detail="Template not found")
    try:
        record = publish_template(template_id, require_test_run=True)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _out(record, include_spec=True)


@router.post("/{template_id}/deprecate", response_model=TemplateOut)
def admin_deprecate_template(
    template_id: str,
    _user: User = Depends(require_role(RoleName.TEMPLATE_EDITOR)),
) -> TemplateOut:
    if get_template(template_id) is None:
        raise HTTPException(status_code=404, detail="Template not found")
    record = deprecate_template(template_id)
    return _out(record, include_spec=True)


@router.post("/{template_id}/test-run", response_model=TestRunOut)
async def admin_test_run(
    template_id: str,
    body: TestRunRequest | None = None,
    _user: User = Depends(require_role(RoleName.TEMPLATE_EDITOR)),
) -> TestRunOut:
    record = get_template(template_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Template not found")
    req = body or TestRunRequest()
    job_id = new_job_id()
    artifact_dir = Path("/tmp/docforge-artifacts") / job_id
    payload = {
        "provider": req.provider,
        "full_name": req.full_name,
        "ref": req.ref,
        "template_slug": record.slug,
        "output_dir": str(artifact_dir),
        "cleanup": False,
    }
    job = JobRecord(id=job_id, job_type="generate_document", payload=payload, status="queued")
    save_job(job)

    try:
        # Run inline for a synchronous pass/fail usable by publish gate.
        result = await run_generate_document(job_id, payload)
        job.status = "completed"
        job.result = result
        job.commit_sha = result.get("commit_sha")
        save_job(job)
        record = mark_test_run(template_id, ok=True, job_id=job_id)
        return TestRunOut(ok=True, job_id=job_id, template=_out(record, include_spec=True))
    except Exception as exc:  # noqa: BLE001
        job.status = "failed"
        job.error = str(exc)
        save_job(job)
        record = mark_test_run(template_id, ok=False, job_id=job_id)
        return TestRunOut(
            ok=False,
            job_id=job_id,
            error=str(exc),
            template=_out(record, include_spec=True),
        )
