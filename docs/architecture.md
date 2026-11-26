# DocForge Architecture (Phase 5)

```
┌─────────┐   JWT/SSE    ┌─────────┐  clone/pin   ┌──────────────────┐
│  web    │ ───────────► │   api   │ ───────────► │ GitHub / GitLab  │
│ Vite    │  /admin      │ FastAPI │              │ or fixture repo  │
│ +admin  │  providers   └────┬────┘              └────────┬─────────┘
└─────────┘                   │ enqueue / inline           │ sandbox
                              ▼                            ▼
                         ┌─────────┐                 analyze+redact
                         │ worker  │                      │
                         │  Arq    │ ◄── Redis ──► progress SSE
                         └────┬────┘                      │
                              │                    DocGenProvider
                              │                    (route/fallback)
                              │                           │
                              ▼              ┌────────────┼────────────┐
                         ┌─────────┐         │            │            │
                         │  MinIO  │    Ollama/OpenAI  Cursor CLI   mock
                         └─────────┘    Anthropic/…    (agent/docker)
                                         Gemini/Bedrock
```

**Invariants:** Templates are immutable per version (SHA-256). Content JSON is keyed by `section_id` only. Section regen/edit/accept change only that section (siblings byte-identical). Citations are content fields pinned to `commit_sha`. Provider API keys are envelope-encrypted and never returned to the browser.

See `docs/DECISIONS.md` and `docs/LICENSES.md`.
