# DocForge Architecture (Phase 1)

```
┌─────────┐   JWT/SSE    ┌─────────┐  clone/pin   ┌──────────────────┐
│  web    │ ───────────► │   api   │ ───────────► │ GitHub / GitLab  │
│ Vite    │              │ FastAPI │              │ or fixture repo  │
└─────────┘              └────┬────┘              └────────┬─────────┘
                              │ enqueue / inline           │ sandbox
                              ▼                            ▼
                         ┌─────────┐                 analyze+redact
                         │ worker  │                      │
                         │  Arq    │ ◄── Redis ──► progress SSE
                         └────┬────┘                      │
                              │                    generate sections
                              │                    (Ollama or mock)
                              │                           │
                              ▼                           ▼
                         ┌─────────┐              render HTML/DOCX/PDF
                         │  MinIO  │              (checksum-sealed template)
                         └─────────┘
```

**Invariant:** Templates are immutable per version (SHA-256). Content JSON is keyed by `section_id` only and merged at render time. Repo data is secret-scanned and wrapped in delimited prompt blocks.

See `docs/DECISIONS.md` and `docs/LICENSES.md`.
