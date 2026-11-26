import { useQuery } from "@tanstack/react-query";
import { AdminShell } from "@/components/AdminShell";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";
import { StatusPill } from "@/components/ui/StatusPill";
import { useAuth } from "@/hooks/useAuth";
import { API_URL } from "@/lib/api";

type HookRow = {
  tool: string;
  available: boolean;
  ok: boolean;
  message: string;
};

async function fetchQualityHooks(token: string): Promise<{ hooks: HookRow[]; note: string }> {
  const response = await fetch(`${API_URL}/admin/quality/hooks`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<{ hooks: HookRow[]; note: string }>;
}

export function AdminQualityPage() {
  const { token } = useAuth();
  const query = useQuery({
    queryKey: ["admin-quality-hooks", token],
    queryFn: () => fetchQualityHooks(token!),
    enabled: Boolean(token),
  });

  return (
    <AdminShell
      title="Quality"
      description="Self-hosted Vale / lychee hooks, hallucination checks, and diagram validation (Phase 5)."
    >
      {query.isLoading ? <LoadingState label="Loading quality hooks…" /> : null}
      {query.isError ? (
        <EmptyState title="Could not load quality hooks" description={(query.error as Error).message} />
      ) : null}
      {query.data ? (
        <div className="space-y-4">
          <p className="text-sm text-muted">{query.data.note}</p>
          <div className="df-panel overflow-x-auto">
            <table className="df-table">
              <thead>
                <tr>
                  <th>Tool</th>
                  <th>Available</th>
                  <th>Status</th>
                  <th>Message</th>
                </tr>
              </thead>
              <tbody>
                {query.data.hooks.map((hook) => (
                  <tr key={hook.tool}>
                    <td className="font-mono text-xs">{hook.tool}</td>
                    <td>
                      <StatusPill
                        label={hook.available ? "installed" : "optional"}
                        tone={hook.available ? "ok" : "warning"}
                      />
                    </td>
                    <td>
                      <StatusPill label={hook.ok ? "ok" : "issues"} tone={hook.ok ? "ok" : "failed"} />
                    </td>
                    <td className="text-sm text-muted">{hook.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-sm text-muted">
            Generation jobs attach hallucination reports and optional diagram artifacts under job quality
            metadata. Install Vale/lychee on the host to enable live prose/link checks.
          </p>
        </div>
      ) : null}
    </AdminShell>
  );
}
