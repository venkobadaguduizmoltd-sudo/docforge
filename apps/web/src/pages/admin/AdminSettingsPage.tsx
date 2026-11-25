import { useQuery } from "@tanstack/react-query";
import { Navigate } from "react-router-dom";
import { AdminShell } from "@/components/AdminShell";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";
import { StatusPill } from "@/components/ui/StatusPill";
import { useAuth } from "@/hooks/useAuth";
import { fetchAdminSettings } from "@/lib/api";
import { canManageSettings } from "@/lib/auth";

export function AdminSettingsPage() {
  const { token, user, isLoading } = useAuth();
  const query = useQuery({
    queryKey: ["admin-settings", token],
    queryFn: () => fetchAdminSettings(token!),
    enabled: Boolean(token) && canManageSettings(user),
  });

  if (!isLoading && user && !canManageSettings(user)) {
    return <Navigate to="/admin" replace />;
  }

  const settings = query.data;

  return (
    <AdminShell
      title="Settings"
      description="Retention and feature-flag placeholders for the control plane. Values are not persisted yet."
    >
      {query.isLoading ? <LoadingState label="Loading settings…" /> : null}
      {query.isError ? (
        <EmptyState title="Could not load settings" description={(query.error as Error).message} />
      ) : null}
      {settings ? (
        <div className="space-y-4">
          <div className="df-panel p-5">
            <p className="df-kicker">Artifact retention</p>
            <p className="mt-2 font-display text-3xl font-semibold tabular-nums">
              {settings.retention_days}{" "}
              <span className="text-lg font-medium text-muted">days</span>
            </p>
            <p className="mt-2 text-sm text-muted">Placeholder — not enforced by the worker yet.</p>
          </div>
          <div className="df-panel overflow-x-auto">
            <table className="df-table">
              <thead>
                <tr>
                  <th>Feature flag</th>
                  <th>State</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(settings.feature_flags).map(([key, enabled]) => (
                  <tr key={key}>
                    <td className="font-mono text-xs">{key}</td>
                    <td>
                      <StatusPill
                        label={enabled ? "on" : "off"}
                        tone={enabled ? "ok" : "inactive"}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-sm text-muted">{settings.note}</p>
        </div>
      ) : null}
    </AdminShell>
  );
}
