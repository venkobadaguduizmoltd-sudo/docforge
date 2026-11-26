# DocForge Architecture Decisions (Phase 0)

Recorded defaults for the foundation scaffold. Change only with an explicit follow-up decision.

## AD-001 — Job queue: Arq + Redis (not Celery)

**Decision:** Use Arq with Redis for background jobs.

**Why:** Arq is Redis-native, async-first, and fits FastAPI/Python 3.12 with less operational surface than Celery+broker extras. Phase 0 only needs a worker that can dequeue stub tasks; Celery’s feature set is not required yet.

**Verified:** Arq 0.26 docs describe RedisSettings.from_dsn and WorkerSettings patterns used in `apps/worker`.

**Revisit when:** Need complex routing, multi-queue priorities, or battle-tested Celery ecosystem integrations.

## AD-002 — Auth: local JWT first; Keycloak later

**Decision:** Phase 0 ships local email/password accounts and JWT bearer tokens with RBAC roles (`admin`, `template-editor`, `editor`, `viewer`).

**Why:** Unblocks development without an IdP dependency. Keycloak (or similar OIDC) can replace token issuance later without rewriting RBAC checks.

## AD-003 — Database: PostgreSQL 16 + pgvector

**Decision:** Primary store is Postgres 16 via the `pgvector/pgvector:pg16` image. Baseline migration enables the `vector` extension.

**Why:** Single database for relational data and future embeddings; avoids a separate vector DB in Phase 0.

## AD-004 — Object storage: MinIO

**Decision:** MinIO provides S3-compatible storage locally and in self-hosted deployments.

**Why:** Free/OSI-friendly, Docker-friendly, API-compatible with future S3 providers.

## AD-005 — Optional local AI: Ollama profile

**Decision:** Ollama is an optional Compose profile (`--profile ollama`). Default AI path remains OpenAI-compatible endpoints.

**Local embeddings note:** Prefer Ollama embedding models (e.g. `nomic-embed-text`) or a local sentence-transformers worker later. Phase 0 does not wire inference; `EMBEDDINGS_PROVIDER=local` is documented in `.env.example`.

## AD-006 — Template / content separation

**Decision:** Templates are versioned and immutable once published (`template_versions.is_immutable`, SHA-256 over canonical JSON). AI and editors write `document_sections.content_json` keyed by `section_id` only.

**Why:** Core product invariant — renderers merge content into templates; checksums verified at render time (Phase 1+).

## AD-007 — Licensing policy

**Decision:** Runtime and CI dependencies must be free/OSI and self-hostable. Optional paid AI providers are integration points later, not required deps. See `docs/LICENSES.md` and the CI license check.

## AD-008 — Monorepo layout

**Decision:** `apps/web`, `apps/api`, `apps/worker`, `packages/shared`, `templates/builtin`, `infra/docker`, `docs`, `.github/workflows`.

**Why:** Clear service boundaries with shared types where useful; Dockerfiles live under `infra/docker`.

## AD-009 — Frontend stack

**Decision:** React 18 + TypeScript + Vite + TanStack Query + Tailwind. Dark mode via a `class` strategy token hook (`useDarkMode`).

**Deferred to later phases:** TipTap, PDF.js, Monaco (named in product context, not required for Phase 0 shell).

## AD-010 — Secrets

**Decision:** No hard-coded production secrets. `.env.example` documents required variables; Compose reads `.env`. Bootstrap admin credentials are env-driven for local/dev only.

## AD-011 — Job progress: SSE over WebSocket

**Decision:** Phase 1 streams job progress with Server-Sent Events (`GET /jobs/{id}/events`) backed by an in-process event history plus optional Redis pub/sub.

**Why:** SSE is simpler for one-way progress, works with FastAPI `StreamingResponse`, and needs no WS protocol negotiation. EventSource cannot set `Authorization`, so Phase 1 also accepts `access_token` query for SSE/preview (tighten later).

## AD-012 — Rendering stack

**Decision:** HTML via Jinja2 theme templates; DOCX via `python-docx`; PDF via ReportLab. All three consume the same validated section content + immutable template spec (checksum verified at render).

**Why:** Avoids HTML→PDF system library chains (WeasyPrint/Cairo) in the MVP container while keeping OSI licenses.

## AD-013 — Repo providers

**Decision:** `RepoProvider` interface with `github`, `gitlab`, and `fixture` adapters. CI and default local runs use `fixture` (copies `apps/api/tests/fixtures/sample_repo`). Live providers use tokens from env/request.

**Why:** Keeps the generation path testable without network; GitHub/GitLab share the same clone/pin contract (ref → SHA, shallow clone, pin on job).

## AD-014 — LLM default for Phase 1

**Decision:** OpenAI-compatible HTTP client targeting Ollama (`OLLAMA_BASE_URL` + `/v1/chat/completions`). `LLM_PROVIDER=mock` is the default in `.env.example` for offline/CI; set `openai_compatible` when Ollama is up.

**Why:** Matches AD-005; mock keeps MVP tests deterministic without a GPU/model pull.

## AD-015 — Analyzer / tree-sitter

**Decision:** Always build file tree + language counts. Symbol extraction uses `tree-sitter` + `tree-sitter-python` when available; JavaScript/TypeScript and fallbacks use regex extractors.

**Why:** Practical Phase 1 coverage without shipping every grammar wheel.

## AD-016 — Prompt injection + secret egress

**Decision:** Redact common secrets before analysis excerpts leave the sandbox. Wrap untrusted repo blobs in `<<<DOCForge_REPO_DATA_BEGIN/END>>>` delimiters with an explicit system guard that ignores instructions inside the block.

## AD-017 — Document store for corrections (in-memory + Alembic)

**Decision:** Phase 2 editable documents live in an in-process `document_store` (same spirit as Phase 1 `job_store`) for CI/dev. Alembic `0003_phase2_corrections` adds Postgres columns for locks, citations, pending suggestions, and provenance (`source_job_id`, `pinned_commit_sha`, template seal).

**Why:** Unblocks section APIs and tests without requiring live Postgres in unit CI; DB schema stays aligned for compose.

**Revisit when:** Persist live documents to Postgres/MinIO and drop the in-memory registry.

## AD-018 — Section-only mutations

**Decision:** Regenerate, manual edit, and accept-suggestion mutate exactly one `section_id`’s content JSON. Sibling sections must remain byte-identical (canonical JSON). Locked sections refuse mutation and are skipped by regenerate-all.

**Why:** Core Phase 2 product invariant alongside template immutability.

## AD-019 — Suggestion mode is non-destructive until accept

**Decision:** `POST .../suggest` stores `pending_suggestion` on the section without creating a content revision. Accept applies proposed content and appends a revision; reject clears the pending payload.

## AD-020 — Versions are full section snapshots

**Decision:** Every successful content/lock mutation appends a `DocumentRevision` with a full per-section snapshot (content, lock, citations, pending suggestion). Diff compares two revision numbers; undo restores `current−1`; restore reapplies a chosen revision then appends a new revision.

## AD-021 — Citations on section content

**Decision:** Citations are content-only fields (`file`, `line`, `end_line`, `commit_sha`, `symbol`) attached when materializing/regenerating from analysis symbols at the document’s pinned commit. They travel in `content_json.citations` and the section `citations` API field. They never alter template structure.

## AD-022 — DocGenProvider interface (model | agent)

**Decision:** Phase 3 introduces `DocGenProvider` in `apps/api/app/ai/` with `kind: model | agent`, `complete`, `list_models`, `test_connection`, and `cancel`. Repo git providers remain under `app/providers/`.

**Why:** One generation contract for Ollama-compatible defaults, optional paid HTTP adapters, and the Cursor CLI agent path without coupling the pipeline to a single SDK.

## AD-023 — HTTP adapters without proprietary SDKs

**Decision:** Model adapters (OpenAI-compatible/Ollama, OpenAI, Anthropic, Azure OpenAI, Gemini/Vertex, Bedrock) use `httpx` only. Paid provider keys are optional; the app runs with mock / Ollama without them.

**Why:** Keeps required dependencies OSI-only (AD-007) and avoids commercial SDK coupling.

## AD-024 — Cursor CLI isolation

**Decision:** `cursor_cli` is `kind=agent`. It runs in a throwaway Docker container when Docker is available, injects only `CURSOR_API_KEY`, never passes `--force` (or related force/yes flags), enforces timeouts, and maps exits to normalized errors. Agent kind always skips retrieval.

**Why:** Limits blast radius of an agent tool that can otherwise mutate host state; product policy separates agent from model+RAG paths.

## AD-025 — Envelope encryption for provider secrets

**Decision:** API keys are stored as Fernet envelope blobs (`wrapped_dek` + `ciphertext`) using `APP_SECRETS_KEY` (falls back to `JWT_SECRET` in development). Admin list/detail responses expose `has_api_key` only — never plaintext or ciphertext to the browser.

**Why:** At-rest protection for optional paid keys without a separate KMS in Phase 3.

## AD-026 — Provider routing, fallback, and budgets

**Decision:** `provider_policies` (in-memory store + Alembic `provider_policies` table) holds primary + fallback chain, daily/monthly token budgets, and `allow_paid_providers`. Exhausted budgets raise `policy_blocked`. Generation uses routing via `ProviderLLMClient` when `LLM_PROVIDER` is not mock.

**Normalized errors:** `auth_failed`, `rate_limited`, `timeout`, `invalid_output`, `policy_blocked`, `provider_unavailable`.

## AD-027 — Template structure JSON Schema

**Decision:** Phase 4 validates every template structure spec with a Draft 2020-12 JSON Schema (`apps/api/app/template_studio/schema.py`) via `jsonschema` (MIT). Specs include `id`, `name`, `slug`, `sections[]` (with optional `instructions` / `content_schema`), plus optional `theme` / `assets` / `tags`.

**Why:** Keeps AI output content-only while making structure authoring machine-checkable before publish.

## AD-028 — Template lifecycle and immutability

**Decision:** Gallery lifecycle is `draft → published → deprecated`. Drafts are mutable; publish seals `sha256` (`compute_spec_sha256`) and sets immutability. Publish requires a successful fixture **test-run**. Clone creates a new draft. Builtins seed as published from `templates/builtin/`.

**Why:** Preserves the core product invariant (immutable templates per version) while enabling an admin studio.

## AD-029 — Prompt / DOCX → draft structure

**Decision:** Prompt-to-template uses a deterministic heuristic (optional provider complete later) then schema-validates. DOCX import walks Heading 1–2 via `python-docx` into sections. Raw YAML round-trips with `PyYAML` (MIT).

**Why:** Fast authoring paths without requiring a live LLM for CI/demo; OSI-only tooling.
