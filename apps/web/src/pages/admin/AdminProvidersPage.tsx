import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState, type FormEvent } from "react";
import { AdminShell } from "@/components/AdminShell";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";
import { StatusPill } from "@/components/ui/StatusPill";
import { useAuth } from "@/hooks/useAuth";
import {
  createAIProvider,
  deleteAIProvider,
  fetchProviderPolicy,
  listAIProviders,
  listProviderModels,
  testAIProvider,
  updateAIProvider,
  updateProviderPolicy,
  type AIProvider,
  type ProviderModel,
  type ProviderTestResult,
} from "@/lib/api";
import { canManageProviders } from "@/lib/auth";

export function AdminProvidersPage() {
  const { token, user } = useAuth();
  const qc = useQueryClient();
  const canWrite = canManageProviders(user);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<ProviderTestResult | null>(null);
  const [models, setModels] = useState<ProviderModel[]>([]);
  const [formError, setFormError] = useState<string | null>(null);

  const providersQuery = useQuery({
    queryKey: ["admin-providers", token],
    queryFn: () => listAIProviders(token!),
    enabled: Boolean(token),
  });

  const policyQuery = useQuery({
    queryKey: ["admin-provider-policy", token],
    queryFn: () => fetchProviderPolicy(token!),
    enabled: Boolean(token),
  });

  const providers = providersQuery.data?.providers ?? [];
  const adapters = providersQuery.data?.adapters ?? [];
  const policy = policyQuery.data;
  const selected = useMemo(
    () => providers.find((p) => p.id === selectedId) ?? null,
    [providers, selectedId],
  );

  const invalidate = async () => {
    await Promise.all([
      qc.invalidateQueries({ queryKey: ["admin-providers", token] }),
      qc.invalidateQueries({ queryKey: ["admin-provider-policy", token] }),
    ]);
  };

  const createMutation = useMutation({
    mutationFn: (body: Parameters<typeof createAIProvider>[1]) => createAIProvider(token!, body),
    onSuccess: async (created) => {
      setFormError(null);
      setSelectedId(created.id);
      await invalidate();
    },
    onError: (err: Error) => setFormError(err.message),
  });

  const updateMutation = useMutation({
    mutationFn: (vars: { id: string; body: Record<string, unknown> }) =>
      updateAIProvider(token!, vars.id, vars.body),
    onSuccess: async () => {
      setFormError(null);
      await invalidate();
    },
    onError: (err: Error) => setFormError(err.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteAIProvider(token!, id),
    onSuccess: async () => {
      setSelectedId(null);
      setTestResult(null);
      setModels([]);
      await invalidate();
    },
  });

  const policyMutation = useMutation({
    mutationFn: (body: Parameters<typeof updateProviderPolicy>[1]) =>
      updateProviderPolicy(token!, body),
    onSuccess: async () => invalidate(),
  });

  const onCreate = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canWrite) return;
    const fd = new FormData(event.currentTarget);
    const adapter = String(fd.get("adapter_type") || "mock");
    const catalog = adapters.find((a) => a.adapter_type === adapter);
    createMutation.mutate({
      name: String(fd.get("name") || "").trim(),
      adapter_type: adapter,
      kind: (catalog?.kind as "model" | "agent") || "model",
      base_url: String(fd.get("base_url") || "") || null,
      default_model: String(fd.get("default_model") || "") || null,
      api_key: String(fd.get("api_key") || "") || null,
      enabled: fd.get("enabled") === "on",
      priority: Number(fd.get("priority") || 100),
    });
    event.currentTarget.reset();
  };

  const onSaveSelected = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canWrite || !selected) return;
    const fd = new FormData(event.currentTarget);
    const body: Record<string, unknown> = {
      name: String(fd.get("name") || "").trim(),
      base_url: String(fd.get("base_url") || "") || null,
      default_model: String(fd.get("default_model") || "") || null,
      enabled: fd.get("enabled") === "on",
      priority: Number(fd.get("priority") || 100),
    };
    const apiKey = String(fd.get("api_key") || "");
    if (apiKey) body.api_key = apiKey;
    updateMutation.mutate({ id: selected.id, body });
  };

  const onSavePolicy = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canWrite) return;
    const fd = new FormData(event.currentTarget);
    const primary = String(fd.get("primary_provider_id") || "") || null;
    const fallbacks = String(fd.get("fallback_provider_ids") || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const daily = String(fd.get("budget_daily_tokens") || "");
    const monthly = String(fd.get("budget_monthly_tokens") || "");
    policyMutation.mutate({
      primary_provider_id: primary,
      fallback_provider_ids: fallbacks,
      budget_daily_tokens: daily ? Number(daily) : null,
      budget_monthly_tokens: monthly ? Number(monthly) : null,
      allow_paid_providers: fd.get("allow_paid_providers") === "on",
      reset_usage: fd.get("reset_usage") === "on",
    });
  };

  const runTest = async (provider: AIProvider) => {
    if (!token) return;
    setTestResult(null);
    try {
      const result = await testAIProvider(token, provider.id);
      setTestResult(result);
    } catch (err) {
      setTestResult({
        ok: false,
        latency_ms: 0,
        message: err instanceof Error ? err.message : "Test failed",
        models_sample: [],
      });
    }
  };

  const loadModels = async (provider: AIProvider) => {
    if (!token) return;
    try {
      const result = await listProviderModels(token, provider.id);
      setModels(result.models);
    } catch (err) {
      setModels([]);
      setFormError(err instanceof Error ? err.message : "Failed to list models");
    }
  };

  return (
    <AdminShell
      title="AI Providers"
      description="Configure model and agent backends, routing/fallback, and budget basics. API keys are write-only and never returned to the browser."
    >
      {providersQuery.isLoading ? <LoadingState label="Loading providers…" /> : null}
      {providersQuery.isError ? (
        <EmptyState
          title="Could not load providers"
          description={(providersQuery.error as Error).message}
        />
      ) : null}

      {providers.length ? (
        <div className="df-panel overflow-x-auto animate-fade-up">
          <table className="df-table">
            <thead>
              <tr>
                <th>Provider</th>
                <th>Kind</th>
                <th>Status</th>
                <th>Key</th>
                <th>Priority</th>
              </tr>
            </thead>
            <tbody>
              {providers.map((row) => {
                const isPrimary = policy?.primary_provider_id === row.id;
                return (
                  <tr
                    key={row.id}
                    className={selectedId === row.id ? "bg-accent-soft/40" : "cursor-pointer"}
                    onClick={() => {
                      setSelectedId(row.id);
                      setTestResult(null);
                      setModels([]);
                    }}
                  >
                    <td>
                      <p className="font-medium text-ink">{row.name}</p>
                      <p className="font-mono text-xs text-muted">{row.adapter_type}</p>
                    </td>
                    <td>
                      <StatusPill label={row.kind} tone={row.kind === "agent" ? "warning" : "default"} />
                      {isPrimary ? (
                        <span className="ml-2 font-mono text-[0.65rem] uppercase tracking-wider text-accent">
                          primary
                        </span>
                      ) : null}
                    </td>
                    <td>
                      <StatusPill
                        label={row.enabled ? "enabled" : "disabled"}
                        tone={row.enabled ? "ok" : "inactive"}
                      />
                    </td>
                    <td className="text-muted">{row.has_api_key ? "set" : "—"}</td>
                    <td className="font-mono text-sm">{row.priority}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        {canWrite ? (
          <form className="df-panel space-y-4 p-5 animate-fade-up" onSubmit={onCreate}>
            <div>
              <p className="df-kicker">Create</p>
              <h2 className="mt-1 font-display text-xl font-semibold text-ink">Add provider</h2>
            </div>
            <label className="block space-y-1 text-sm">
              <span className="text-muted">Name</span>
              <input className="df-input" name="name" required placeholder="My Ollama" />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-muted">Adapter</span>
              <select className="df-input" name="adapter_type" defaultValue="openai_compatible">
                {adapters.map((a) => (
                  <option key={a.adapter_type} value={a.adapter_type}>
                    {a.adapter_type} ({a.kind})
                  </option>
                ))}
              </select>
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-muted">Base URL</span>
              <input className="df-input" name="base_url" placeholder="http://localhost:11434" />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-muted">Default model</span>
              <input className="df-input" name="default_model" placeholder="llama3.2" />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-muted">API key (write-only)</span>
              <input className="df-input" name="api_key" type="password" autoComplete="off" />
            </label>
            <div className="flex flex-wrap items-center gap-4">
              <label className="inline-flex items-center gap-2 text-sm text-muted">
                <input type="checkbox" name="enabled" defaultChecked />
                Enabled
              </label>
              <label className="inline-flex items-center gap-2 text-sm text-muted">
                Priority
                <input className="df-input w-24" name="priority" type="number" defaultValue={100} />
              </label>
            </div>
            <button className="df-btn-primary" type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creating…" : "Create provider"}
            </button>
          </form>
        ) : (
          <EmptyState
            title="Read-only"
            description="Template editors can list, test, and inspect models. Admin role is required to create or edit providers."
          />
        )}

        <div className="space-y-6">
          {selected ? (
            <form className="df-panel space-y-4 p-5 animate-fade-up" onSubmit={onSaveSelected}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="df-kicker">Selected</p>
                  <h2 className="mt-1 font-display text-xl font-semibold text-ink">{selected.name}</h2>
                  <p className="font-mono text-xs text-muted">{selected.id}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="df-btn-secondary"
                    onClick={() => runTest(selected)}
                  >
                    Test connection
                  </button>
                  <button
                    type="button"
                    className="df-btn-secondary"
                    onClick={() => loadModels(selected)}
                  >
                    List models
                  </button>
                </div>
              </div>
              <label className="block space-y-1 text-sm">
                <span className="text-muted">Name</span>
                <input
                  className="df-input"
                  name="name"
                  defaultValue={selected.name}
                  key={`${selected.id}-name`}
                  disabled={!canWrite}
                  required
                />
              </label>
              <label className="block space-y-1 text-sm">
                <span className="text-muted">Base URL</span>
                <input
                  className="df-input"
                  name="base_url"
                  defaultValue={selected.base_url ?? ""}
                  key={`${selected.id}-url`}
                  disabled={!canWrite}
                />
              </label>
              <label className="block space-y-1 text-sm">
                <span className="text-muted">Default model</span>
                <input
                  className="df-input"
                  name="default_model"
                  defaultValue={selected.default_model ?? ""}
                  key={`${selected.id}-model`}
                  disabled={!canWrite}
                />
              </label>
              {canWrite ? (
                <label className="block space-y-1 text-sm">
                  <span className="text-muted">
                    Rotate API key {selected.has_api_key ? "(currently set)" : ""}
                  </span>
                  <input className="df-input" name="api_key" type="password" autoComplete="off" />
                </label>
              ) : null}
              <div className="flex flex-wrap items-center gap-4">
                <label className="inline-flex items-center gap-2 text-sm text-muted">
                  <input
                    type="checkbox"
                    name="enabled"
                    defaultChecked={selected.enabled}
                    key={`${selected.id}-en`}
                    disabled={!canWrite}
                  />
                  Enabled
                </label>
                <label className="inline-flex items-center gap-2 text-sm text-muted">
                  Priority
                  <input
                    className="df-input w-24"
                    name="priority"
                    type="number"
                    defaultValue={selected.priority}
                    key={`${selected.id}-pri`}
                    disabled={!canWrite}
                  />
                </label>
              </div>
              {canWrite ? (
                <div className="flex flex-wrap gap-2">
                  <button className="df-btn-primary" type="submit" disabled={updateMutation.isPending}>
                    Save changes
                  </button>
                  <button
                    type="button"
                    className="df-btn-ghost text-danger"
                    onClick={() => {
                      if (window.confirm(`Delete provider “${selected.name}”?`)) {
                        deleteMutation.mutate(selected.id);
                      }
                    }}
                  >
                    Delete
                  </button>
                </div>
              ) : null}
              {testResult ? (
                <div className="rounded-[var(--radius-md)] border border-border bg-canvas/60 p-3 text-sm">
                  <StatusPill
                    label={testResult.ok ? "ok" : "failed"}
                    tone={testResult.ok ? "ok" : "failed"}
                  />
                  <p className="mt-2 text-muted">{testResult.message}</p>
                  <p className="mt-1 font-mono text-xs text-muted">
                    {testResult.latency_ms.toFixed(1)} ms
                    {testResult.models_sample.length
                      ? ` · sample: ${testResult.models_sample.join(", ")}`
                      : ""}
                  </p>
                </div>
              ) : null}
              {models.length ? (
                <div>
                  <p className="df-kicker mb-2">Models</p>
                  <ul className="max-h-40 space-y-1 overflow-auto font-mono text-xs text-muted">
                    {models.map((m) => (
                      <li key={m.id}>{m.name || m.id}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </form>
          ) : (
            <EmptyState
              title="Select a provider"
              description="Choose a row to test the connection, list models, or edit settings."
            />
          )}
        </div>
      </div>

      {policy ? (
        <form className="df-panel space-y-4 p-5 animate-fade-up" onSubmit={onSavePolicy}>
          <div>
            <p className="df-kicker">Routing & budgets</p>
            <h2 className="mt-1 font-display text-xl font-semibold text-ink">Provider policy</h2>
            <p className="df-subtitle !mt-1 text-sm">
              Primary and fallback chain for generation. Usage counters are basic Phase 3 tracking.
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block space-y-1 text-sm">
              <span className="text-muted">Primary provider</span>
              <select
                className="df-input"
                name="primary_provider_id"
                defaultValue={policy.primary_provider_id ?? ""}
                key={`pri-${policy.updated_at}`}
                disabled={!canWrite}
              >
                <option value="">— env / settings fallback —</option>
                {providers.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-muted">Fallback IDs (comma-separated)</span>
              <input
                className="df-input"
                name="fallback_provider_ids"
                defaultValue={policy.fallback_provider_ids.join(", ")}
                key={`fb-${policy.updated_at}`}
                disabled={!canWrite}
                placeholder="uuid-1, uuid-2"
              />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-muted">Daily token budget</span>
              <input
                className="df-input"
                name="budget_daily_tokens"
                type="number"
                defaultValue={policy.budget_daily_tokens ?? ""}
                key={`d-${policy.updated_at}`}
                disabled={!canWrite}
                placeholder="unlimited"
              />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-muted">Monthly token budget</span>
              <input
                className="df-input"
                name="budget_monthly_tokens"
                type="number"
                defaultValue={policy.budget_monthly_tokens ?? ""}
                key={`m-${policy.updated_at}`}
                disabled={!canWrite}
                placeholder="unlimited"
              />
            </label>
          </div>
          <p className="font-mono text-xs text-muted">
            Used today: {policy.tokens_used_today} · month: {policy.tokens_used_month}
          </p>
          {canWrite ? (
            <div className="flex flex-wrap items-center gap-4">
              <label className="inline-flex items-center gap-2 text-sm text-muted">
                <input
                  type="checkbox"
                  name="allow_paid_providers"
                  defaultChecked={policy.allow_paid_providers}
                  key={`paid-${policy.updated_at}`}
                />
                Allow paid providers
              </label>
              <label className="inline-flex items-center gap-2 text-sm text-muted">
                <input type="checkbox" name="reset_usage" />
                Reset usage counters
              </label>
              <button className="df-btn-primary" type="submit" disabled={policyMutation.isPending}>
                Save policy
              </button>
            </div>
          ) : null}
        </form>
      ) : null}

      {formError ? (
        <p className="text-sm text-danger" role="alert">
          {formError}
        </p>
      ) : null}
    </AdminShell>
  );
}
