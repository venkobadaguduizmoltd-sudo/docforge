import { useState, type FormEvent } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { AppShell } from "@/components/AppShell";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusPill } from "@/components/ui/StatusPill";
import { useAuth } from "@/hooks/useAuth";
import {
  API_URL,
  fetchJob,
  jobEventsUrl,
  materializeDocument,
  startGenerateJob,
  type DocForgeDocument,
  type Job,
} from "@/lib/api";

export function GeneratePage() {
  const { token } = useAuth();
  const [provider, setProvider] = useState("fixture");
  const [fullName, setFullName] = useState("docforge/sample");
  const [ref, setRef] = useState("main");
  const [jobId, setJobId] = useState<string | null>(null);
  const [events, setEvents] = useState<string[]>([]);
  const [documentId, setDocumentId] = useState<string | null>(null);

  const jobQuery = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => fetchJob(token!, jobId!),
    enabled: Boolean(token && jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "completed" || status === "failed" ? false : 1000;
    },
  });

  const mutation = useMutation({
    mutationFn: () =>
      startGenerateJob(token!, {
        provider,
        full_name: fullName,
        ref,
        template_slug: "tech-overview",
      }),
    onSuccess: (job: Job) => {
      setJobId(job.id);
      setDocumentId(null);
      setEvents([]);
      if (!token) return;
      const source = new EventSource(jobEventsUrl(job.id, token));
      source.onmessage = (message) => {
        setEvents((prev) => [...prev.slice(-40), message.data]);
        try {
          const parsed = JSON.parse(message.data) as { stage?: string };
          if (parsed.stage === "completed" || parsed.stage === "failed") {
            source.close();
          }
        } catch {
          /* ignore non-json */
        }
      };
      source.onerror = () => source.close();
    },
  });

  const openDoc = useMutation({
    mutationFn: () => materializeDocument(token!, jobId!),
    onSuccess: (doc: DocForgeDocument) => setDocumentId(doc.id),
  });

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    mutation.mutate();
  };

  const job = jobQuery.data;

  return (
    <AppShell>
      <div className="space-y-8">
        <PageHeader
          kicker="Pipeline"
          title="Generate"
          description="Generate from a repo into an immutable template, then open the document workspace for section regen, suggestions, locks, and versions."
        />

        {!token ? (
          <EmptyState
            title="Sign in required"
            description="Generation jobs need an authenticated session."
            action={
              <Link to="/login" className="df-btn-primary">
                Sign in
              </Link>
            }
          />
        ) : (
          <form onSubmit={onSubmit} className="df-panel max-w-lg space-y-4 p-5 animate-fade-up">
            <label className="block space-y-1.5 text-sm">
              <span className="text-muted">Provider</span>
              <select
                className="df-input"
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
              >
                <option value="fixture">fixture</option>
                <option value="github">github</option>
                <option value="gitlab">gitlab</option>
              </select>
            </label>
            <label className="block space-y-1.5 text-sm">
              <span className="text-muted">Full name</span>
              <input
                className="df-input"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
              />
            </label>
            <label className="block space-y-1.5 text-sm">
              <span className="text-muted">Ref</span>
              <input className="df-input" value={ref} onChange={(e) => setRef(e.target.value)} />
            </label>
            <button type="submit" disabled={mutation.isPending} className="df-btn-primary">
              {mutation.isPending ? "Starting…" : "Generate document"}
            </button>
            {mutation.isError ? (
              <p className="text-sm text-danger" role="alert">
                {(mutation.error as Error).message}
              </p>
            ) : null}
          </form>
        )}

        {job ? (
          <div className="df-panel max-w-2xl space-y-3 p-5 animate-fade-in">
            <div className="flex flex-wrap items-center gap-3">
              <p className="df-kicker">Job {job.id.slice(0, 8)}…</p>
              <StatusPill label={job.status} />
            </div>
            {job.commit_sha ? (
              <p className="font-mono text-xs text-muted">Pinned SHA: {job.commit_sha}</p>
            ) : null}
            {job.status === "completed" && token ? (
              <div className="flex flex-wrap gap-3 pt-1">
                <a
                  className="df-btn-secondary"
                  href={`${API_URL}/jobs/${job.id}/preview?access_token=${encodeURIComponent(token)}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  HTML preview
                </a>
                <button
                  type="button"
                  className="df-btn-primary"
                  disabled={openDoc.isPending}
                  onClick={() => openDoc.mutate()}
                >
                  {openDoc.isPending ? "Opening…" : "Open in document editor"}
                </button>
                {documentId ? (
                  <Link className="df-btn-secondary" to={`/documents/${documentId}`}>
                    Edit sections / versions
                  </Link>
                ) : null}
              </div>
            ) : null}
            {job.error ? <p className="text-sm text-danger">{job.error}</p> : null}
            {openDoc.isError ? (
              <p className="text-sm text-danger">{(openDoc.error as Error).message}</p>
            ) : null}
            {events.length ? (
              <pre className="max-h-48 overflow-auto rounded-md border border-border bg-canvas p-3 font-mono text-xs text-muted">
                {events.join("\n")}
              </pre>
            ) : job.status === "running" || job.status === "queued" ? (
              <p className="text-sm text-muted">Waiting for progress events…</p>
            ) : null}
          </div>
        ) : null}
      </div>
    </AppShell>
  );
}
