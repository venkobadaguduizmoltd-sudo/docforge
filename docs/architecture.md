# DocForge Architecture (Phase 6)

```
┌─────────┐   JWT/SSE    ┌─────────┐  clone/pin   ┌──────────────────────────┐
│  web    │ ───────────► │   api   │ ───────────► │ GitHub/GitLab/Bitbucket  │
│ Vite    │  /admin      │ FastAPI │              │ Azure/Gitea/generic/upload│
│ +admin  │  +webhooks   └────┬────┘              │ + fixture                │
└─────────┘                   │                   └────────────┬─────────────┘
                              │ enqueue / inline               │ sandbox
                              ▼                                ▼
                         ┌─────────┐                     analyze+redact
                         │ worker  │                          │
                         │  Arq    │ ◄── Redis ──► progress SSE
                         └────┬────┘                          │
                              │                        DocGenProvider
                              ▼                               │
                         ┌─────────┐              docs-as-code PR/MR + status
                         │  MinIO  │              drift → incremental regen
                         └─────────┘
```

**Invariants:** Templates are immutable per version (SHA-256). Content JSON is keyed by `section_id` only. Section regen/edit/accept change only that section (siblings byte-identical). Citations are content fields pinned to `commit_sha`. Provider API keys are envelope-encrypted and never returned to the browser. Webhooks verify signatures and reject replays before normalizing events.

See `docs/DECISIONS.md` and `docs/LICENSES.md`.
