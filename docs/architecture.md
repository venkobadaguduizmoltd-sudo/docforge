# DocForge Architecture (Phase 0 pointer)

```
┌─────────┐     JWT      ┌─────────┐     SQL      ┌──────────────────┐
│  web    │ ───────────► │   api   │ ──────────► │ Postgres 16+vec  │
│ Vite/React             │ FastAPI │             └──────────────────┘
└─────────┘              └────┬────┘
                              │ enqueue
                              ▼
                         ┌─────────┐     Redis    ┌───────┐
                         │ worker  │ ◄─────────── │ redis │
                         │  Arq    │              └───────┘
                         └────┬────┘
                              │ objects
                              ▼
                         ┌─────────┐
                         │  MinIO  │
                         └─────────┘

Optional: Ollama (--profile ollama) for local OpenAI-compatible inference.
```

**Invariant:** Templates are immutable per version (SHA-256). Content JSON is keyed by section id and merged at render time.

See `docs/DECISIONS.md` for defaults and `docs/LICENSES.md` for licensing policy.
