# DocForge

AI documentation platform: generate professional docs from Git repositories into admin-defined **immutable templates**, with live preview and section-level corrections.

> Phase 4 — Admin template studio (gallery, prompt/DOCX import, publish). See [docs/architecture.md](docs/architecture.md) and [docs/DECISIONS.md](docs/DECISIONS.md).

## Core principle

Templates (structure + rendering assets) are **immutable per version** (SHA-256). The AI only produces **content JSON keyed by section id**. Renderers merge content into templates.

## Stack

| Layer | Choice |
|-------|--------|
| Web | React, TypeScript, Vite, TanStack Query, Tailwind |
| API | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 |
| Worker | Arq + Redis |
| Data | PostgreSQL 16 + pgvector, MinIO |
| Optional AI | Ollama default; optional OpenAI/Anthropic/Azure/Gemini/Bedrock/Cursor CLI keys |
| Render | Jinja2 HTML, python-docx, ReportLab PDF |
| Admin | `/admin/templates` studio; `/admin/providers` CRUD/test/routing |

## Quick start (Docker Compose)

```bash
cp .env.example .env
# Edit JWT_SECRET and passwords before any shared/deployed use
docker compose up --build
```

Services:

| Service | URL |
|---------|-----|
| Web | http://localhost:5173 |
| API | http://localhost:8000 (`/health`, `/docs`) |
| MinIO API / Console | http://localhost:9000 / http://localhost:9001 |
| Postgres | localhost:5432 |
| Redis | localhost:6379 |

Optional local LLM:

```bash
docker compose --profile ollama up --build
```

**Local embeddings:** with the `ollama` profile running, pull an embedding model (for example `ollama pull nomic-embed-text`). Phase 0 does not invoke embeddings; later phases use `OLLAMA_BASE_URL` / `EMBEDDINGS_PROVIDER=local`.

Default bootstrap admin (from `.env.example`): `admin@localhost` / `admin_change_me`.

### Phase 1 MVP flow

1. Sign in at http://localhost:5173/login  
2. Open **Generate** (`/generate`) and run with provider `fixture` (no tokens needed).  
3. Watch job status / SSE stages; open HTML preview; download DOCX/PDF from `/jobs/{id}/artifacts/{kind}`.  
4. For live GitHub/GitLab: set `GITHUB_TOKEN` / `GITLAB_TOKEN`, choose provider, pass `full_name` + `ref`.  
5. For real LLM output: `docker compose --profile ollama up`, set `LLM_PROVIDER=openai_compatible`, pull a chat model.

Offline pipeline test:

```bash
cd apps/api && pip install -r requirements.txt
LLM_PROVIDER=mock pytest -q
```

### Windows 11 / WSL2

1. Install [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/) with the **WSL2** backend enabled.
2. Clone/copy this repo into your WSL2 filesystem (e.g. `~/code/docforge`), not a slow `/mnt/c/...` path.
3. In a WSL2 terminal: `cp .env.example .env && docker compose up --build`.
4. Open the web UI from Windows at http://localhost:5173 (ports publish to the host).

## Local development without full Compose

```bash
# API
cd apps/api && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Requires Postgres reachable via DATABASE_URL
alembic upgrade head
uvicorn app.main:app --reload

# Worker
cd apps/worker && pip install -r requirements.txt
arq worker.main.WorkerSettings

# Web
cd apps/web && npm install && npm run dev
```

## License policy

Only free/OSI self-hostable dependencies for the core platform. See [docs/LICENSES.md](docs/LICENSES.md). CI runs `scripts/check_licenses.py`.

## Repository layout

```
apps/web          Frontend
apps/api          FastAPI + Alembic
apps/worker       Arq workers
packages/shared   Shared types/constants
templates/builtin Builtin template stubs
infra/docker      Dockerfiles
docs/             Decisions, licenses, architecture
.github/workflows CI
```
