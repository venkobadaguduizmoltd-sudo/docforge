import { useState, type FormEvent } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/AppShell";
import { fetchJob, jobEventsUrl, startGenerateJob, type Job } from "@/lib/api";

const TOKEN_KEY = "docforge-token";
const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export function GeneratePage() {
  const token = typeof window !== "undefined" ? window.localStorage.getItem(TOKEN_KEY) : null;
  const [provider, setProvider] = useState("fixture");
  const [fullName, setFullName] = useState("docforge/sample");
  const [ref, setRef] = useState("main");
  const [jobId, setJobId] = useState<string | null>(null);
  const [events, setEvents] = useState<string[]>([]);

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

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    mutation.mutate();
  };

  const job = jobQuery.data;

  return (
    <AppShell title="DocForge">
      <section className="space-y-6">
        <div>
          <h2 className="text-3xl font-semibold tracking-tight">Generate</h2>
          <p className="mt-2 max-w-xl text-muted">
            Phase 1 MVP: clone a repo (fixture/GitHub/GitLab), analyze, generate section content, render
            HTML/DOCX/PDF.
          </p>
        </div>
        {!token ? (
          <p className="text-muted">Sign in first to run a generation job.</p>
        ) : (
          <form onSubmit={onSubmit} className="max-w-lg space-y-4">
            <label className="block space-y-1 text-sm">
              <span className="text-muted">Provider</span>
              <select
                className="w-full rounded-md border border-border bg-surface px-3 py-2"
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
              >
                <option value="fixture">fixture</option>
                <option value="github">github</option>
                <option value="gitlab">gitlab</option>
              </select>
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-muted">Full name</span>
              <input
                className="w-full rounded-md border border-border bg-surface px-3 py-2"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
              />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="text-muted">Ref</span>
              <input
                className="w-full rounded-md border border-border bg-surface px-3 py-2"
                value={ref}
                onChange={(e) => setRef(e.target.value)}
              />
            </label>
            <button
              type="submit"
              disabled={mutation.isPending}
              className="rounded-md bg-accent px-4 py-2.5 font-medium text-white dark:text-canvas"
            >
              {mutation.isPending ? "Starting…" : "Generate document"}
            </button>
          </form>
        )}
        {job ? (
          <div className="space-y-2 rounded-lg border border-border bg-surface/70 p-4">
            <p className="font-mono text-xs uppercase tracking-wider text-muted">Job {job.id}</p>
            <p className="text-lg font-medium">Status: {job.status}</p>
            {job.commit_sha ? <p className="text-sm text-muted">Pinned SHA: {job.commit_sha}</p> : null}
            {job.status === "completed" && token ? (
              <p className="text-sm">
                <a
                  className="text-accent underline"
                  href={`${API_URL}/jobs/${job.id}/preview?access_token=${encodeURIComponent(token)}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open HTML preview
                </a>
              </p>
            ) : null}
            {job.error ? <p className="text-sm text-red-600">{job.error}</p> : null}
            {events.length ? (
              <pre className="max-h-48 overflow-auto text-xs text-muted">{events.join("\n")}</pre>
            ) : null}
          </div>
        ) : null}
      </section>
    </AppShell>
  );
}
