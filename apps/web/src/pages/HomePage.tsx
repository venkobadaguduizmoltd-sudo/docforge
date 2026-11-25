import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { AppShell } from "@/components/AppShell";
import { fetchHealth, fetchMe } from "@/lib/api";

const TOKEN_KEY = "docforge-token";

export function HomePage() {
  const token = typeof window !== "undefined" ? window.localStorage.getItem(TOKEN_KEY) : null;

  const health = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    retry: false,
  });

  const me = useQuery({
    queryKey: ["me", token],
    queryFn: () => fetchMe(token!),
    enabled: Boolean(token),
    retry: false,
  });

  return (
    <AppShell>
      <section className="space-y-6">
        <div>
          <h2 className="text-3xl font-semibold tracking-tight">Workspace</h2>
          <p className="mt-2 max-w-xl text-muted">
            Phase 1 MVP: generate docs from GitHub/GitLab/fixture repos into an immutable template.
          </p>
        </div>
        <dl className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-lg border border-border bg-surface/70 p-4">
            <dt className="font-mono text-xs uppercase tracking-wider text-muted">API</dt>
            <dd className="mt-2 text-lg font-medium">
              {health.isLoading ? "Checking…" : health.data?.status === "ok" ? "Healthy" : "Unavailable"}
            </dd>
          </div>
          <div className="rounded-lg border border-border bg-surface/70 p-4">
            <dt className="font-mono text-xs uppercase tracking-wider text-muted">Session</dt>
            <dd className="mt-2 text-lg font-medium">
              {token ? (me.data ? me.data.email : me.isError ? "Expired" : "Loading…") : "Signed out"}
            </dd>
          </div>
        </dl>
        <div className="flex flex-wrap gap-3">
          {!token ? (
            <Link to="/login" className="inline-flex rounded-md bg-accent px-4 py-2.5 font-medium text-white dark:text-canvas">
              Go to login
            </Link>
          ) : (
            <Link to="/generate" className="inline-flex rounded-md bg-accent px-4 py-2.5 font-medium text-white dark:text-canvas">
              Generate document
            </Link>
          )}
        </div>
      </section>
    </AppShell>
  );
}
