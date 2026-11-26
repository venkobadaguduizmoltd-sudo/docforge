# DocForge Dependency Licenses (Phase 0)

Policy: only free / OSI-approved / self-hostable dependencies for the core platform. Optional paid AI providers may be added later as runtime integrations (API keys), not as mandatory libraries.

## Allowed license families

- MIT
- Apache-2.0
- BSD-2-Clause / BSD-3-Clause
- ISC
- MPL-2.0
- PostgreSQL
- BlueOak-1.0.0
- Unlicense / CC0-1.0 (for trivial utilities)
- PSF-2.0 (Python)

## Disallowed for core deps

- Proprietary / commercial-only SDKs required at build or runtime
- AGPL-only packages that would force unwanted copyleft on the product (revisit case-by-case)
- Non-OSI “source available” with usage restrictions (e.g. SSPL-only services as hard deps)

## Primary stack licenses (summary)

| Component | Package / Image | License (typical) |
|-----------|-----------------|-------------------|
| API framework | FastAPI | MIT |
| ASGI server | Uvicorn | BSD-3-Clause |
| ORM | SQLAlchemy | MIT |
| Migrations | Alembic | MIT |
| Validation | Pydantic | MIT |
| Postgres driver | psycopg | LGPL-3.0 (client library; self-hostable) |
| Auth helpers | python-jose, passlib, bcrypt | MIT / Apache-2.0 / Apache-2.0 |
| Jobs | Arq, redis-py | MIT |
| Tests / lint | pytest, ruff, mypy | MIT |
| JSON Schema | jsonschema | MIT |
| YAML | PyYAML | MIT |
| Frontend | React, Vite, TanStack Query, Tailwind | MIT |
| TypeScript / ESLint | TypeScript, typescript-eslint | Apache-2.0 / MIT |
| Database image | pgvector/pgvector:pg16 | PostgreSQL + pgvector license |
| Cache | redis:7-alpine | BSD-3-Clause (Redis) |
| Object storage | MinIO | AGPL-3.0 (self-hostable; optional S3 swap later) |
| Optional LLM | Ollama | MIT |
| HTML templates | Jinja2 | BSD-3-Clause |
| DOCX | python-docx | MIT |
| PDF | ReportLab | BSD-3-Clause |
| Symbols | tree-sitter, tree-sitter-python | MIT |

## MinIO note

MinIO server is AGPL-3.0 and self-hostable. DocForge talks to it over the S3 API; swapping to another S3-compatible store does not require linking MinIO code. Documented here for operator awareness.

## CI enforcement

`scripts/check_licenses.py` fails the build if a declared dependency maps to a disallowed license class. Update this file when adding packages.
