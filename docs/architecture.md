# DocForge Architecture (Phase 2)

```
┌─────────┐   JWT/SSE    ┌─────────┐  clone/pin   ┌──────────────────┐
│  web    │ ───────────► │   api   │ ───────────► │ GitHub / GitLab  │
│ Vite    │  documents/  │ FastAPI │              │ or fixture repo  │
└─────────┘  sections    └────┬────┘              └────────┬─────────┘
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
                         ┌─────────┐     materialize → document_store
                         │  MinIO  │     edit/regen/suggest/lock/versions
                         └─────────┘     render HTML/DOCX/PDF (sealed)
```

**Invariants:** Templates are immutable per version (SHA-256). Content JSON is keyed by `section_id` only. Section regen/edit/accept change only that section (siblings byte-identical). Citations are content fields pinned to `commit_sha`.

See `docs/DECISIONS.md` and `docs/LICENSES.md`.
