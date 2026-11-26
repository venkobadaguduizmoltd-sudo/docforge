"""DocForge FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api import (
    admin,
    auth,
    documents,
    health,
    jobs,
    providers_admin,
    quality,
    repos,
    templates,
    templates_admin,
)
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import Role, User  # noqa: F401 — ensure metadata registered
from app.rbac.roles import ALL_ROLES, RoleName


def seed_roles_and_admin() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        for role_name in ALL_ROLES:
            existing = db.scalar(select(Role).where(Role.name == role_name.value))
            if existing is None:
                db.add(Role(name=role_name.value, description=f"{role_name.value} role"))

        admin = db.scalar(select(User).where(User.email == settings.bootstrap_admin_email))
        if admin is None:
            db.add(
                User(
                    email=settings.bootstrap_admin_email,
                    hashed_password=hash_password(settings.bootstrap_admin_password),
                    full_name="Bootstrap Admin",
                    role=RoleName.ADMIN.value,
                    is_active=True,
                )
            )
        db.commit()
    except Exception:
        # Allow API unit paths / OpenAPI import without a live database.
        db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    seed_roles_and_admin()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title=settings.app_name, version="0.6.0", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        # Try Live / Cursor VM proxy hosts when the browser hits the API port directly.
        allow_origin_regex=r"https?://.*\.cursorvm\.com",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(health.router)
    application.include_router(auth.router)
    application.include_router(repos.router)
    application.include_router(templates.router)
    application.include_router(jobs.router)
    application.include_router(documents.router)
    application.include_router(admin.router)
    application.include_router(providers_admin.router)
    application.include_router(templates_admin.router)
    application.include_router(quality.router)
    return application


app = create_app()
