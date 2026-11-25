import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { AppShell } from "@/components/AppShell";
import {
  acceptSuggestion,
  editSection,
  fetchDocument,
  fetchVersions,
  lockSection,
  regenerateAllUnlocked,
  regenerateSection,
  rejectSuggestion,
  restoreVersion,
  suggestSection,
  undoDocument,
  unlockSection,
  type DocumentSection,
} from "@/lib/api";

const TOKEN_KEY = "docforge-token";

function sectionSummary(section: DocumentSection): string {
  const summary = section.content_json.summary;
  return typeof summary === "string" ? summary : "";
}

function sectionBullets(section: DocumentSection): string[] {
  const bullets = section.content_json.bullets;
  return Array.isArray(bullets) ? bullets.map(String) : [];
}

export function DocumentPage() {
  const { documentId = "" } = useParams();
  const token = typeof window !== "undefined" ? window.localStorage.getItem(TOKEN_KEY) : null;
  const queryClient = useQueryClient();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [prompt, setPrompt] = useState("");
  const [draftSummary, setDraftSummary] = useState("");
  const [draftBullets, setDraftBullets] = useState("");

  const docQuery = useQuery({
    queryKey: ["document", documentId],
    queryFn: () => fetchDocument(token!, documentId),
    enabled: Boolean(token && documentId),
  });

  const versionsQuery = useQuery({
    queryKey: ["document-versions", documentId],
    queryFn: () => fetchVersions(token!, documentId),
    enabled: Boolean(token && documentId),
  });

  const doc = docQuery.data;
  const active = useMemo(() => {
    if (!doc) return null;
    const id = activeId ?? doc.sections[0]?.section_id ?? null;
    return doc.sections.find((s) => s.section_id === id) ?? null;
  }, [doc, activeId]);

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ["document", documentId] });
    await queryClient.invalidateQueries({ queryKey: ["document-versions", documentId] });
  };

  const run = useMutation({
    mutationFn: async (fn: () => Promise<unknown>) => fn(),
    onSuccess: invalidate,
  });

  const selectSection = (section: DocumentSection) => {
    setActiveId(section.section_id);
    setDraftSummary(sectionSummary(section));
    setDraftBullets(sectionBullets(section).join("\n"));
    setPrompt("");
  };

  if (!token) {
    return (
      <AppShell title="DocForge">
        <p className="text-muted">
          Sign in first. <Link to="/login">Login</Link>
        </p>
      </AppShell>
    );
  }

  return (
    <AppShell title="DocForge">
      <section className="space-y-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="font-mono text-xs uppercase tracking-wider text-muted">
              <Link to="/generate" className="underline">
                Generate
              </Link>{" "}
              / document
            </p>
            <h2 className="text-3xl font-semibold tracking-tight">{doc?.title ?? "Loading…"}</h2>
            {doc ? (
              <p className="mt-2 text-sm text-muted">
                Rev {doc.current_revision} · pinned {(doc.pinned_commit_sha ?? "").slice(0, 8)} ·{" "}
                {doc.template_slug}
              </p>
            ) : null}
          </div>
          {doc ? (
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="rounded-md border border-border px-3 py-2 text-sm"
                disabled={run.isPending}
                onClick={() =>
                  run.mutate(() => regenerateAllUnlocked(token, doc.id, prompt || undefined))
                }
              >
                Regen unlocked
              </button>
              <button
                type="button"
                className="rounded-md border border-border px-3 py-2 text-sm"
                disabled={run.isPending}
                onClick={() => run.mutate(() => undoDocument(token, doc.id))}
              >
                Undo
              </button>
            </div>
          ) : null}
        </div>

        {docQuery.isError ? (
          <p className="text-sm text-red-600">{(docQuery.error as Error).message}</p>
        ) : null}

        {doc ? (
          <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
            <aside className="space-y-2">
              {doc.sections.map((section) => (
                <button
                  key={section.section_id}
                  type="button"
                  onClick={() => selectSection(section)}
                  className={`block w-full rounded-md border px-3 py-2 text-left text-sm ${
                    active?.section_id === section.section_id
                      ? "border-accent bg-surface"
                      : "border-border bg-surface/40"
                  }`}
                >
                  <span className="font-medium">{section.section_id}</span>
                  {section.is_locked ? (
                    <span className="ml-2 text-xs text-muted">locked</span>
                  ) : null}
                  {section.pending_suggestion ? (
                    <span className="ml-2 text-xs text-accent">suggestion</span>
                  ) : null}
                </button>
              ))}
            </aside>

            {active ? (
              <div className="space-y-4 rounded-lg border border-border bg-surface/70 p-4">
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="rounded-md border border-border px-3 py-1.5 text-sm"
                    disabled={run.isPending || active.is_locked}
                    onClick={() =>
                      run.mutate(() =>
                        regenerateSection(token, doc.id, active.section_id, prompt || undefined),
                      )
                    }
                  >
                    Regenerate
                  </button>
                  <button
                    type="button"
                    className="rounded-md border border-border px-3 py-1.5 text-sm"
                    disabled={run.isPending || active.is_locked}
                    onClick={() =>
                      run.mutate(() =>
                        suggestSection(token, doc.id, active.section_id, prompt || undefined),
                      )
                    }
                  >
                    Suggest
                  </button>
                  {active.is_locked ? (
                    <button
                      type="button"
                      className="rounded-md border border-border px-3 py-1.5 text-sm"
                      disabled={run.isPending}
                      onClick={() => run.mutate(() => unlockSection(token, doc.id, active.section_id))}
                    >
                      Unlock
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="rounded-md border border-border px-3 py-1.5 text-sm"
                      disabled={run.isPending}
                      onClick={() => run.mutate(() => lockSection(token, doc.id, active.section_id))}
                    >
                      Lock
                    </button>
                  )}
                </div>

                <label className="block space-y-1 text-sm">
                  <span className="text-muted">Follow-up / suggestion prompt</span>
                  <input
                    className="w-full rounded-md border border-border bg-canvas px-3 py-2"
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    placeholder="Optional instruction for AI"
                  />
                </label>

                <label className="block space-y-1 text-sm">
                  <span className="text-muted">Summary</span>
                  <textarea
                    className="min-h-28 w-full rounded-md border border-border bg-canvas px-3 py-2"
                    value={draftSummary || sectionSummary(active)}
                    onChange={(e) => setDraftSummary(e.target.value)}
                    disabled={active.is_locked}
                  />
                </label>

                <label className="block space-y-1 text-sm">
                  <span className="text-muted">Bullets (one per line)</span>
                  <textarea
                    className="min-h-24 w-full rounded-md border border-border bg-canvas px-3 py-2"
                    value={draftBullets || sectionBullets(active).join("\n")}
                    onChange={(e) => setDraftBullets(e.target.value)}
                    disabled={active.is_locked}
                  />
                </label>

                <button
                  type="button"
                  className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white dark:text-canvas"
                  disabled={run.isPending || active.is_locked}
                  onClick={() =>
                    run.mutate(() =>
                      editSection(token, doc.id, active.section_id, {
                        ...active.content_json,
                        summary: draftSummary || sectionSummary(active),
                        bullets: (draftBullets || sectionBullets(active).join("\n"))
                          .split("\n")
                          .map((b) => b.trim())
                          .filter(Boolean),
                      }),
                    )
                  }
                >
                  Save section
                </button>

                {active.pending_suggestion ? (
                  <div className="space-y-2 rounded-md border border-accent/40 bg-canvas p-3">
                    <p className="text-sm font-medium">Pending suggestion</p>
                    <pre className="max-h-40 overflow-auto text-xs text-muted">
                      {JSON.stringify(active.pending_suggestion.proposed, null, 2)}
                    </pre>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        className="rounded-md bg-accent px-3 py-1.5 text-sm text-white dark:text-canvas"
                        onClick={() =>
                          run.mutate(() => acceptSuggestion(token, doc.id, active.section_id))
                        }
                      >
                        Accept
                      </button>
                      <button
                        type="button"
                        className="rounded-md border border-border px-3 py-1.5 text-sm"
                        onClick={() =>
                          run.mutate(() => rejectSuggestion(token, doc.id, active.section_id))
                        }
                      >
                        Reject
                      </button>
                    </div>
                  </div>
                ) : null}

                <div>
                  <p className="text-sm font-medium">Citations</p>
                  <ul className="mt-1 space-y-1 text-sm text-muted">
                    {(active.citations.length ? active.citations : []).map((c, i) => (
                      <li key={`${c.file}-${c.line}-${i}`} className="font-mono text-xs">
                        {c.file}
                        {c.line != null ? `:${c.line}` : ""}
                        {c.symbol ? ` (${c.symbol})` : ""}
                        {c.commit_sha ? ` @ ${c.commit_sha.slice(0, 8)}` : ""}
                      </li>
                    ))}
                    {!active.citations.length ? <li>None</li> : null}
                  </ul>
                </div>
              </div>
            ) : null}
          </div>
        ) : null}

        {versionsQuery.data?.length ? (
          <div className="space-y-2">
            <h3 className="text-lg font-medium">Versions</h3>
            <ul className="space-y-1 text-sm">
              {[...versionsQuery.data].reverse().map((rev) => (
                <li key={rev.revision_number} className="flex items-center gap-3 text-muted">
                  <span className="font-mono">r{rev.revision_number}</span>
                  <span>{rev.note ?? "—"}</span>
                  <button
                    type="button"
                    className="underline"
                    disabled={run.isPending || !doc}
                    onClick={() =>
                      doc && run.mutate(() => restoreVersion(token, doc.id, rev.revision_number))
                    }
                  >
                    Restore
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {run.isError ? <p className="text-sm text-red-600">{(run.error as Error).message}</p> : null}
      </section>
    </AppShell>
  );
}
