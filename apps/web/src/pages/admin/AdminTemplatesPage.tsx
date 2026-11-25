import { useQuery } from "@tanstack/react-query";
import { AdminShell } from "@/components/AdminShell";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";
import { StatusPill } from "@/components/ui/StatusPill";
import { useAuth } from "@/hooks/useAuth";
import { listBuiltinTemplates } from "@/lib/api";

export function AdminTemplatesPage() {
  const { token } = useAuth();
  const query = useQuery({
    queryKey: ["admin-templates", token],
    queryFn: () => listBuiltinTemplates(token!),
    enabled: Boolean(token),
  });

  const templates = query.data?.templates ?? [];

  return (
    <AdminShell
      title="Templates"
      description="Read-only builtin catalog from the API. Template studio (create/version/publish) arrives in Phase 4."
    >
      {query.isLoading ? <LoadingState label="Loading templates…" /> : null}
      {query.isError ? (
        <EmptyState
          title="Could not load templates"
          description={(query.error as Error).message}
        />
      ) : null}
      {!query.isLoading && !query.isError && templates.length === 0 ? (
        <EmptyState
          title="No templates yet"
          description="Builtin templates will appear here. Custom template management is coming in Phase 4."
        />
      ) : null}
      {templates.length ? (
        <div className="df-panel overflow-x-auto">
          <table className="df-table">
            <thead>
              <tr>
                <th>Slug</th>
                <th>Name</th>
                <th>Checksum</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {templates.map((tpl) => (
                <tr key={tpl.slug}>
                  <td className="font-mono text-xs">{tpl.slug}</td>
                  <td>{tpl.name ?? "—"}</td>
                  <td className="font-mono text-xs text-muted">{tpl.sha256.slice(0, 12)}…</td>
                  <td>
                    <StatusPill label={tpl.immutable ? "immutable" : "mutable"} tone="ok" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      <p className="text-sm text-muted">Template authoring UI: coming in Phase 4.</p>
    </AdminShell>
  );
}
