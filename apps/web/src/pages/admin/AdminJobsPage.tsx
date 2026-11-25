import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { AdminShell } from "@/components/AdminShell";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";
import { StatusPill } from "@/components/ui/StatusPill";
import { useAuth } from "@/hooks/useAuth";
import { listJobs } from "@/lib/api";

export function AdminJobsPage() {
  const { token } = useAuth();
  const query = useQuery({
    queryKey: ["admin-jobs", token],
    queryFn: () => listJobs(token!),
    enabled: Boolean(token),
    refetchInterval: 4000,
  });

  const jobs = query.data?.jobs ?? [];

  return (
    <AdminShell
      title="Jobs console"
      description="In-process generation jobs for this API lifetime. Persistence and richer filters arrive later."
    >
      {query.isLoading ? <LoadingState label="Loading jobs…" /> : null}
      {query.isError ? (
        <EmptyState title="Could not load jobs" description={(query.error as Error).message} />
      ) : null}
      {!query.isLoading && !query.isError && jobs.length === 0 ? (
        <EmptyState
          title="No jobs yet"
          description="Run a generation from the Generate screen to populate this console."
          action={
            <Link to="/generate" className="df-btn-primary">
              Open Generate
            </Link>
          }
        />
      ) : null}
      {jobs.length ? (
        <div className="df-panel overflow-x-auto">
          <table className="df-table">
            <thead>
              <tr>
                <th>Job</th>
                <th>Type</th>
                <th>Status</th>
                <th>Commit</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id}>
                  <td className="font-mono text-xs">{job.id.slice(0, 8)}…</td>
                  <td>{job.job_type}</td>
                  <td>
                    <StatusPill label={job.status} />
                  </td>
                  <td className="font-mono text-xs text-muted">
                    {(job.commit_sha ?? "—").toString().slice(0, 8)}
                  </td>
                  <td className="text-muted">{new Date(job.updated_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </AdminShell>
  );
}
