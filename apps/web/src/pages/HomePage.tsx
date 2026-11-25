import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { AppShell } from "@/components/AppShell";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusPill } from "@/components/ui/StatusPill";
import { useAuth } from "@/hooks/useAuth";
import { fetchHealth, listDocuments } from "@/lib/api";

export function HomePage() {
  const { token, user, isLoading: authLoading } = useAuth();

  const health = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    retry: false,
  });

  const docs = useQuery({
    queryKey: ["documents", token],
    queryFn: () => listDocuments(token!),
    enabled: Boolean(token),
    retry: false,
  });

  return (
    <AppShell>
      <div className="space-y-8">
        <PageHeader
          kicker="Workspace"
          title="Docs"
          description="Materialized documents from completed generate jobs. Open one to edit sections, suggestions, locks, and versions."
          actions={
            token ? (
              <Link to="/generate" className="df-btn-primary">
                Generate
              </Link>
            ) : (
              <Link to="/login" className="df-btn-primary">
                Sign in
              </Link>
            )
          }
        />

        <div className="flex flex-wrap gap-3 text-sm">
          <StatusPill
            label={
              health.isLoading
                ? "API…"
                : health.data?.status === "ok"
                  ? "API healthy"
                  : "API unavailable"
            }
            tone={health.data?.status === "ok" ? "ok" : health.isError ? "failed" : "default"}
          />
          <StatusPill
            label={
              !token
                ? "Signed out"
                : authLoading
                  ? "Session…"
                  : user
                    ? user.email
                    : "Session expired"
            }
            tone={user ? "ok" : "inactive"}
          />
        </div>

        {!token ? (
          <EmptyState
            title="Sign in to see documents"
            description="Use the bootstrap admin account to generate docs and open the document workspace."
            action={
              <Link to="/login" className="df-btn-primary">
                Go to login
              </Link>
            }
          />
        ) : docs.isLoading ? (
          <LoadingState label="Loading documents…" rows={4} />
        ) : docs.isError ? (
          <EmptyState
            title="Could not load documents"
            description={(docs.error as Error).message}
          />
        ) : !docs.data?.length ? (
          <EmptyState
            title="No documents yet"
            description="Generate from a repository, then open the result in the document editor."
            action={
              <Link to="/generate" className="df-btn-primary">
                Generate document
              </Link>
            }
          />
        ) : (
          <div className="df-panel overflow-x-auto animate-fade-in">
            <table className="df-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Template</th>
                  <th>Revision</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {docs.data.map((doc) => (
                  <tr key={doc.id}>
                    <td>
                      <Link className="font-medium text-accent underline-offset-2 hover:underline" to={`/documents/${doc.id}`}>
                        {doc.title}
                      </Link>
                    </td>
                    <td className="font-mono text-xs text-muted">{doc.template_slug}</td>
                    <td className="tabular-nums">r{doc.current_revision}</td>
                    <td className="text-muted">{new Date(doc.updated_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AppShell>
  );
}
