"""End-to-end document generation pipeline."""

from __future__ import annotations

import json
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from app.analysis.analyzer import analyze_repository
from app.core.config import get_settings
from app.generation.generator import generate_document_content
from app.generation.llm import get_llm_client
from app.pipeline.progress import publish_progress
from app.providers.factory import get_repo_provider
from app.rendering import render_docx, render_html, render_pdf
from app.services.templates import compute_spec_sha256, load_builtin_template


async def run_generate_document(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    payload keys:
      provider, full_name, ref, template_slug (default tech-overview),
      output_dir (optional), token/api_base optional
    """
    settings = get_settings()
    provider_name = payload.get("provider", "fixture")
    full_name = payload.get("full_name", "docforge/sample")
    ref = payload.get("ref", "main")
    template_slug = payload.get("template_slug", "tech-overview")

    await publish_progress(job_id, "started", {"provider": provider_name, "ref": ref})

    provider = get_repo_provider(
        provider_name,
        token=payload.get("token"),
        api_base=payload.get("api_base"),
    )
    await publish_progress(job_id, "authenticating", {})
    await provider.authenticate()

    await publish_progress(job_id, "resolving_ref", {"ref": ref})
    commit_sha = await provider.resolve_ref(full_name, ref)
    await publish_progress(job_id, "commit_pinned", {"commit_sha": commit_sha})

    work_root = Path(payload.get("work_root") or tempfile.mkdtemp(prefix="docforge-"))
    clone_dir = work_root / "repo"
    output_dir = Path(payload.get("output_dir") or (work_root / "out"))
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        await publish_progress(job_id, "cloning", {"depth": 1})
        clone = await provider.shallow_clone(full_name, ref, clone_dir)
        # Prefer resolved pin
        commit_sha = clone.commit_sha or commit_sha

        await publish_progress(job_id, "analyzing", {})
        analysis = analyze_repository(clone_dir)
        await publish_progress(
            job_id,
            "analyzed",
            {
                "files": len(analysis.files),
                "languages": analysis.languages,
                "secrets_redacted": analysis.secret_findings_count,
            },
        )

        await publish_progress(job_id, "loading_template", {"slug": template_slug})
        try:
            loaded = load_builtin_template(template_slug, settings.resolved_templates_root)
            spec = loaded["spec"]
            sha256 = loaded["sha256"]
            theme_dir = loaded["theme_dir"]
        except FileNotFoundError:
            # Phase 4 studio templates (draft test-run / published gallery)
            from app.template_studio.store import resolve_spec_for_generation

            studio = resolve_spec_for_generation(template_slug)
            if studio is None:
                raise
            spec = studio["spec"]
            sha256 = studio["sha256"]
            # Fall back to shared builtin theme assets when studio has no disk theme.
            fallback = load_builtin_template("tech-overview", settings.resolved_templates_root)
            theme_dir = fallback["theme_dir"]
        # Verify immutability seal
        if compute_spec_sha256(spec) != sha256:
            raise RuntimeError("Template checksum failed")

        llm = get_llm_client()

        async def on_progress(stage: str, detail: dict[str, Any]) -> None:
            await publish_progress(job_id, stage, detail)

        content = await generate_document_content(
            sections=spec["sections"],
            analysis=analysis,
            llm=llm,
            on_progress=on_progress,
        )
        content_dict = {sid: section.model_dump() for sid, section in content.items()}

        await publish_progress(job_id, "rendering", {"formats": ["html", "docx", "pdf"]})
        html = render_html(
            template_spec=spec,
            content=content,
            theme_dir=theme_dir,
            expected_sha256=sha256,
        )
        html_path = output_dir / "preview.html"
        html_path.write_text(html, encoding="utf-8")
        docx_path = render_docx(
            template_spec=spec,
            content=content,
            output_path=output_dir / "document.docx",
            expected_sha256=sha256,
        )
        pdf_path = render_pdf(
            template_spec=spec,
            content=content,
            output_path=output_dir / "document.pdf",
            expected_sha256=sha256,
        )

        result = {
            "job_id": job_id,
            "commit_sha": commit_sha,
            "provider": provider_name,
            "full_name": full_name,
            "ref": ref,
            "template_slug": template_slug,
            "template_sha256": sha256,
            "content": content_dict,
            "analysis": {
                "files": analysis.files,
                "languages": analysis.languages,
                "symbols": [s.__dict__ for s in analysis.symbols[:50]],
                "secret_findings_count": analysis.secret_findings_count,
            },
            "artifacts": {
                "html": str(html_path),
                "docx": str(docx_path),
                "pdf": str(pdf_path),
            },
        }
        (output_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        await publish_progress(job_id, "completed", {"artifacts": result["artifacts"]})
        return result
    except Exception as exc:
        await publish_progress(job_id, "failed", {"error": str(exc)})
        raise
    finally:
        if payload.get("cleanup", True) and not payload.get("output_dir"):
            shutil.rmtree(work_root, ignore_errors=True)


def new_job_id() -> str:
    return str(uuid.uuid4())
