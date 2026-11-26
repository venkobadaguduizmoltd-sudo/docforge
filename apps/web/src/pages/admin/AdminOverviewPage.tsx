import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { AdminShell } from "@/components/AdminShell";
import { LoadingState } from "@/components/ui/LoadingState";
import { StatusPill } from "@/components/ui/StatusPill";
import { useAuth } from "@/hooks/useAuth";
import { listBuiltinTemplates, listDocuments, listJobs } from "@/lib/api";

export function AdminOverviewPage() {
  const { token } = useAuth();

  const templates = useQuery({
    queryKey: ["admin-templates", token],
    queryFn: () => listBuiltinTemplates(token!),
    enabled: Boolean(token),
  });
  const jobs = useQuery({
    queryKey: ["admin-jobs", token],
    queryFn: () => listJobs(token!),
    enabled: Boolean(token),
  });
  const docs = useQuery({
    queryKey: ["admin-docs", token],
    queryFn: () => listDocuments(token!),
    enabled: Boolean(token),
  });

  const loading = templates.isLoading || jobs.isLoading || docs.isLoading;
  const metrics = [
    {
      label: "Templates",
      value: templates.data?.templates.length ?? "—",
      hint: "Builtin catalog",
      to: "/admin/templates",
    },
    {
      label: "Jobs",
      value: jobs.data?.jobs.length ?? "—",
      hint: "In-process registry",
      to: "/admin/jobs",
    },
    {
      label: "Documents",
      value: docs.data?.length ?? "—",
      hint: "Materialized workspace",
      to: "/",
    },
    {
      label: "Providers",
      value: "1",
      hint: "Fixture only · Phase 3",
      to: "/admin/providers",
    },
  ];

  return (
    <AdminShell
      title="Overview"
      description="Admin home for templates, AI providers, users, jobs, and settings."
    >
      {loading ? <LoadingState label="Loading metrics…" rows={2} /> : null}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => (
          <Link key={metric.label} to={metric.to} className="df-panel block p-4 transition hover:border-accent/40">
            <p className="df-kicker">{metric.label}</p>
            <p className="mt-3 font-display text-3xl font-semibold tabular-nums text-ink">{metric.value}</p>
            <p className="mt-2 text-sm text-muted">{metric.hint}</p>
          </Link>
        ))}
      </div>
      <div className="df-panel p-5">
        <div className="flex flex-wrap items-center gap-3">
          <StatusPill label="Shell live" tone="ok" />
          <StatusPill label="Phase 3 AI providers" tone="ok" />
          <StatusPill label="Phase 4 template studio" tone="ok" />
        </div>
        <p className="mt-4 text-sm leading-relaxed text-muted">
          Use the sidebar for the template studio, AI providers, users, jobs, and settings.
        </p>
      </div>
    </AdminShell>
  );
}
