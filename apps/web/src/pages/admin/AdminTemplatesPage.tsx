import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { AdminShell } from "@/components/AdminShell";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";
import { StatusPill } from "@/components/ui/StatusPill";
import { useAuth } from "@/hooks/useAuth";
import {
  cloneStudioTemplate,
  createStudioTemplate,
  deprecateStudioTemplate,
  fetchStudioTemplateYaml,
  getStudioTemplate,
  importDocxTemplate,
  listStudioTemplates,
  promptStudioTemplate,
  publishStudioTemplate,
  putStudioTemplateSpec,
  putStudioTemplateYaml,
  testRunStudioTemplate,
  type StudioTemplate,
} from "@/lib/api";

type SectionDraft = {
  id: string;
  title: string;
  description?: string;
  instructions?: string;
};

type EditorTab = "visual" | "json" | "yaml";

function statusTone(status: StudioTemplate["status"]): "ok" | "warning" | "danger" | "neutral" {
  if (status === "published") return "ok";
  if (status === "draft") return "warning";
  return "neutral";
}

export function AdminTemplatesPage() {
  const { token } = useAuth();
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tagFilter, setTagFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [tab, setTab] = useState<EditorTab>("visual");
  const [sections, setSections] = useState<SectionDraft[]>([]);
  const [jsonText, setJsonText] = useState("");
  const [yamlText, setYamlText] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [promptText, setPromptText] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  const listQuery = useQuery({
    queryKey: ["admin-studio-templates", token, tagFilter, statusFilter],
    queryFn: () =>
      listStudioTemplates(token!, {
        tag: tagFilter || undefined,
        status: statusFilter || undefined,
      }),
    enabled: Boolean(token),
  });

  const detailQuery = useQuery({
    queryKey: ["admin-studio-template", token, selectedId],
    queryFn: () => getStudioTemplate(token!, selectedId!),
    enabled: Boolean(token && selectedId),
  });

  const templates = listQuery.data?.templates ?? [];
  const selected = detailQuery.data ?? null;
  const editable = selected?.status === "draft" && !selected.immutable;

  useEffect(() => {
    if (!selected?.spec) return;
    setSections(
      selected.spec.sections.map((s) => ({
        id: s.id,
        title: s.title,
        description: s.description,
        instructions: s.instructions,
      })),
    );
    setJsonText(JSON.stringify(selected.spec, null, 2));
  }, [selected?.id, selected?.sha256, selected?.spec]);

  useEffect(() => {
    if (!token || !selectedId || tab !== "yaml") return;
    void fetchStudioTemplateYaml(token, selectedId)
      .then((r) => setYamlText(r.yaml_text))
      .catch((err: Error) => setFormError(err.message));
  }, [token, selectedId, tab, selected?.sha256]);

  const tags = useMemo(() => {
    const set = new Set<string>();
    for (const t of templates) for (const tag of t.tags) set.add(tag);
    return [...set].sort();
  }, [templates]);

  const invalidate = async (id?: string) => {
    await qc.invalidateQueries({ queryKey: ["admin-studio-templates", token] });
    if (id) await qc.invalidateQueries({ queryKey: ["admin-studio-template", token, id] });
  };

  const createMutation = useMutation({
    mutationFn: (name: string) => createStudioTemplate(token!, { name, tags: ["studio"] }),
    onSuccess: async (tpl) => {
      setSelectedId(tpl.id);
      setMessage(`Created draft ${tpl.slug}`);
      await invalidate(tpl.id);
    },
    onError: (err: Error) => setFormError(err.message),
  });

  const promptMutation = useMutation({
    mutationFn: () => promptStudioTemplate(token!, { description: promptText }),
    onSuccess: async (tpl) => {
      setSelectedId(tpl.id);
      setPromptText("");
      setMessage(`Drafted from prompt: ${tpl.name}`);
      await invalidate(tpl.id);
    },
    onError: (err: Error) => setFormError(err.message),
  });

  const saveVisualMutation = useMutation({
    mutationFn: async () => {
      if (!selected?.spec) throw new Error("No spec loaded");
      const spec = {
        ...selected.spec,
        sections: sections.map((s) => ({
          id: s.id,
          title: s.title,
          description: s.description || "",
          instructions: s.instructions || "",
        })),
      };
      return putStudioTemplateSpec(token!, selected.id, spec);
    },
    onSuccess: async (tpl) => {
      setMessage("Saved visual sections");
      setFormError(null);
      await invalidate(tpl.id);
    },
    onError: (err: Error) => setFormError(err.message),
  });

  const saveJsonMutation = useMutation({
    mutationFn: async () => {
      const spec = JSON.parse(jsonText) as Record<string, unknown>;
      return putStudioTemplateSpec(token!, selectedId!, spec);
    },
    onSuccess: async (tpl) => {
      setMessage("Saved JSON spec");
      await invalidate(tpl.id);
    },
    onError: (err: Error) => setFormError(err.message),
  });

  const saveYamlMutation = useMutation({
    mutationFn: () => putStudioTemplateYaml(token!, selectedId!, yamlText),
    onSuccess: async (tpl) => {
      setMessage("Saved YAML spec");
      await invalidate(tpl.id);
    },
    onError: (err: Error) => setFormError(err.message),
  });

  const testMutation = useMutation({
    mutationFn: () => testRunStudioTemplate(token!, selectedId!),
    onSuccess: async (result) => {
      setMessage(result.ok ? `Test run OK (job ${result.job_id})` : `Test run failed: ${result.error}`);
      await invalidate(selectedId!);
    },
    onError: (err: Error) => setFormError(err.message),
  });

  const publishMutation = useMutation({
    mutationFn: () => publishStudioTemplate(token!, selectedId!),
    onSuccess: async (tpl) => {
      setMessage(`Published ${tpl.slug}`);
      await invalidate(tpl.id);
    },
    onError: (err: Error) => setFormError(err.message),
  });

  const deprecateMutation = useMutation({
    mutationFn: () => deprecateStudioTemplate(token!, selectedId!),
    onSuccess: async (tpl) => {
      setMessage(`Deprecated ${tpl.slug}`);
      await invalidate(tpl.id);
    },
    onError: (err: Error) => setFormError(err.message),
  });

  const cloneMutation = useMutation({
    mutationFn: () => cloneStudioTemplate(token!, selectedId!),
    onSuccess: async (tpl) => {
      setSelectedId(tpl.id);
      setMessage(`Cloned to ${tpl.slug}`);
      await invalidate(tpl.id);
    },
    onError: (err: Error) => setFormError(err.message),
  });

  const onCreate = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);
    const fd = new FormData(event.currentTarget);
    const name = String(fd.get("name") || "").trim();
    if (!name) return;
    createMutation.mutate(name);
    event.currentTarget.reset();
  };

  const onImportDocx = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);
    const fd = new FormData(event.currentTarget);
    const file = fd.get("file");
    if (!(file instanceof File) || !file.size) {
      setFormError("Choose a DOCX file");
      return;
    }
    try {
      const tpl = await importDocxTemplate(token!, file);
      setSelectedId(tpl.id);
      setMessage(`Imported ${tpl.name}`);
      await invalidate(tpl.id);
      event.currentTarget.reset();
    } catch (err) {
      setFormError((err as Error).message);
    }
  };

  const moveSection = (index: number, delta: number) => {
    setSections((prev) => {
      const next = [...prev];
      const target = index + delta;
      if (target < 0 || target >= next.length) return prev;
      const tmp = next[index]!;
      next[index] = next[target]!;
      next[target] = tmp;
      return next;
    });
  };

  const addSection = () => {
    const n = sections.length + 1;
    setSections((prev) => [
      ...prev,
      {
        id: `section_${n}`,
        title: `Section ${n}`,
        description: "",
        instructions: "",
      },
    ]);
  };

  return (
    <AdminShell
      title="Templates"
      description="Gallery, visual/raw editor, prompt & DOCX import, test-run, and publish lifecycle."
    >
      {formError ? (
        <p className="text-sm text-danger" role="alert">
          {formError}
        </p>
      ) : null}
      {message ? <p className="text-sm text-muted">{message}</p> : null}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <div className="space-y-4">
          <div className="df-panel space-y-3 p-4">
            <p className="df-kicker">Gallery filters</p>
            <div className="flex flex-wrap gap-2">
              <select
                className="df-input max-w-[10rem]"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="">All statuses</option>
                <option value="draft">draft</option>
                <option value="published">published</option>
                <option value="deprecated">deprecated</option>
              </select>
              <select
                className="df-input max-w-[12rem]"
                value={tagFilter}
                onChange={(e) => setTagFilter(e.target.value)}
              >
                <option value="">All tags</option>
                {tags.map((tag) => (
                  <option key={tag} value={tag}>
                    {tag}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {listQuery.isLoading ? <LoadingState label="Loading gallery…" /> : null}
          {listQuery.isError ? (
            <EmptyState title="Could not load templates" description={(listQuery.error as Error).message} />
          ) : null}

          <div className="df-panel overflow-x-auto">
            <table className="df-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Status</th>
                  <th>Tags</th>
                </tr>
              </thead>
              <tbody>
                {templates.map((tpl) => (
                  <tr
                    key={tpl.id}
                    className={selectedId === tpl.id ? "bg-canvas/60" : "cursor-pointer"}
                    onClick={() => {
                      setSelectedId(tpl.id);
                      setFormError(null);
                      setMessage(null);
                    }}
                  >
                    <td>
                      <div className="font-medium">{tpl.name}</div>
                      <div className="font-mono text-xs text-muted">{tpl.slug}</div>
                    </td>
                    <td>
                      <StatusPill label={tpl.status} tone={statusTone(tpl.status)} />
                    </td>
                    <td className="text-xs text-muted">{tpl.tags.join(", ") || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <form onSubmit={onCreate} className="df-panel space-y-3 p-4">
            <p className="df-kicker">New blank draft</p>
            <input className="df-input" name="name" placeholder="Template name" required />
            <button type="submit" className="df-btn-primary" disabled={createMutation.isPending}>
              Create draft
            </button>
          </form>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              setFormError(null);
              promptMutation.mutate();
            }}
            className="df-panel space-y-3 p-4"
          >
            <p className="df-kicker">Prompt → structure</p>
            <textarea
              className="df-input min-h-[5rem]"
              value={promptText}
              onChange={(e) => setPromptText(e.target.value)}
              placeholder="Describe the document type…"
              required
            />
            <button type="submit" className="df-btn-secondary" disabled={promptMutation.isPending}>
              Draft from prompt
            </button>
          </form>

          <form onSubmit={onImportDocx} className="df-panel space-y-3 p-4">
            <p className="df-kicker">Import DOCX headings</p>
            <input className="df-input" type="file" name="file" accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document" />
            <button type="submit" className="df-btn-secondary">
              Import DOCX
            </button>
          </form>
        </div>

        <div className="space-y-4">
          {!selectedId ? (
            <EmptyState
              title="Select a template"
              description="Pick a gallery row to edit sections, run a fixture test, or publish."
            />
          ) : detailQuery.isLoading ? (
            <LoadingState label="Loading template…" />
          ) : selected ? (
            <>
              <div className="df-panel space-y-3 p-4">
                <div className="flex flex-wrap items-center gap-3">
                  <h2 className="font-display text-xl font-semibold">{selected.name}</h2>
                  <StatusPill label={selected.status} tone={statusTone(selected.status)} />
                  {selected.last_test_run_ok ? <StatusPill label="test-run ok" tone="ok" /> : null}
                </div>
                <p className="text-sm text-muted">{selected.description || "No description"}</p>
                <p className="font-mono text-xs text-muted">
                  sha256 {(selected.sha256 ?? "").slice(0, 16)}… · source {selected.source}
                </p>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="df-btn-secondary"
                    onClick={() => testMutation.mutate()}
                    disabled={testMutation.isPending}
                  >
                    Test run (fixture)
                  </button>
                  <button
                    type="button"
                    className="df-btn-primary"
                    onClick={() => publishMutation.mutate()}
                    disabled={!editable || publishMutation.isPending}
                  >
                    Publish
                  </button>
                  <button
                    type="button"
                    className="df-btn-secondary"
                    onClick={() => cloneMutation.mutate()}
                    disabled={cloneMutation.isPending}
                  >
                    Clone
                  </button>
                  <button
                    type="button"
                    className="df-btn-secondary"
                    onClick={() => deprecateMutation.mutate()}
                    disabled={deprecateMutation.isPending || selected.status === "deprecated"}
                  >
                    Deprecate
                  </button>
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                {(["visual", "json", "yaml"] as EditorTab[]).map((key) => (
                  <button
                    key={key}
                    type="button"
                    className={tab === key ? "df-btn-primary" : "df-btn-secondary"}
                    onClick={() => setTab(key)}
                  >
                    {key === "visual" ? "Visual" : key.toUpperCase()}
                  </button>
                ))}
              </div>

              {tab === "visual" ? (
                <div className="df-panel space-y-3 p-4">
                  {sections.map((section, index) => (
                    <div key={`${section.id}-${index}`} className="space-y-2 border-b border-border/60 pb-3">
                      <div className="flex flex-wrap gap-2">
                        <input
                          className="df-input max-w-[8rem] font-mono text-xs"
                          value={section.id}
                          disabled={!editable}
                          onChange={(e) =>
                            setSections((prev) =>
                              prev.map((s, i) => (i === index ? { ...s, id: e.target.value } : s)),
                            )
                          }
                        />
                        <input
                          className="df-input flex-1"
                          value={section.title}
                          disabled={!editable}
                          onChange={(e) =>
                            setSections((prev) =>
                              prev.map((s, i) => (i === index ? { ...s, title: e.target.value } : s)),
                            )
                          }
                        />
                        <button
                          type="button"
                          className="df-btn-secondary"
                          disabled={!editable || index === 0}
                          onClick={() => moveSection(index, -1)}
                        >
                          ↑
                        </button>
                        <button
                          type="button"
                          className="df-btn-secondary"
                          disabled={!editable || index === sections.length - 1}
                          onClick={() => moveSection(index, 1)}
                        >
                          ↓
                        </button>
                        <button
                          type="button"
                          className="df-btn-secondary"
                          disabled={!editable || sections.length <= 1}
                          onClick={() => setSections((prev) => prev.filter((_, i) => i !== index))}
                        >
                          Remove
                        </button>
                      </div>
                      <textarea
                        className="df-input min-h-[2.5rem]"
                        placeholder="Instructions"
                        disabled={!editable}
                        value={section.instructions ?? ""}
                        onChange={(e) =>
                          setSections((prev) =>
                            prev.map((s, i) => (i === index ? { ...s, instructions: e.target.value } : s)),
                          )
                        }
                      />
                    </div>
                  ))}
                  <div className="flex flex-wrap gap-2">
                    <button type="button" className="df-btn-secondary" disabled={!editable} onClick={addSection}>
                      Add section
                    </button>
                    <button
                      type="button"
                      className="df-btn-primary"
                      disabled={!editable || saveVisualMutation.isPending}
                      onClick={() => saveVisualMutation.mutate()}
                    >
                      Save sections
                    </button>
                  </div>
                </div>
              ) : null}

              {tab === "json" ? (
                <div className="df-panel space-y-3 p-4">
                  <textarea
                    className="df-input min-h-[22rem] font-mono text-xs"
                    value={jsonText}
                    disabled={!editable}
                    onChange={(e) => setJsonText(e.target.value)}
                  />
                  <button
                    type="button"
                    className="df-btn-primary"
                    disabled={!editable || saveJsonMutation.isPending}
                    onClick={() => saveJsonMutation.mutate()}
                  >
                    Save JSON
                  </button>
                </div>
              ) : null}

              {tab === "yaml" ? (
                <div className="df-panel space-y-3 p-4">
                  <textarea
                    className="df-input min-h-[22rem] font-mono text-xs"
                    value={yamlText}
                    disabled={!editable}
                    onChange={(e) => setYamlText(e.target.value)}
                  />
                  <button
                    type="button"
                    className="df-btn-primary"
                    disabled={!editable || saveYamlMutation.isPending}
                    onClick={() => saveYamlMutation.mutate()}
                  >
                    Save YAML
                  </button>
                </div>
              ) : null}
            </>
          ) : (
            <EmptyState title="Template missing" description="Select another row from the gallery." />
          )}
        </div>
      </div>
    </AdminShell>
  );
}
