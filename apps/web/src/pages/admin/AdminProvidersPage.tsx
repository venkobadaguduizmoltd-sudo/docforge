import { AdminShell } from "@/components/AdminShell";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusPill } from "@/components/ui/StatusPill";

const STUBS = [
  { id: "fixture", name: "Fixture / mock", status: "available", note: "Local demo path" },
  { id: "ollama", name: "Ollama (OpenAI-compatible)", status: "phase-3", note: "Adapter pending" },
  { id: "openai", name: "OpenAI", status: "phase-3", note: "Optional paid provider" },
];

export function AdminProvidersPage() {
  return (
    <AdminShell
      title="AI Providers"
      description="Provider configuration is deferred to Phase 3. This list is a stub so admins can see where credentials and models will live."
    >
      <div className="df-panel overflow-x-auto">
        <table className="df-table">
          <thead>
            <tr>
              <th>Provider</th>
              <th>Status</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>
            {STUBS.map((row) => (
              <tr key={row.id}>
                <td>
                  <p className="font-medium text-ink">{row.name}</p>
                  <p className="font-mono text-xs text-muted">{row.id}</p>
                </td>
                <td>
                  <StatusPill
                    label={row.status}
                    tone={row.status === "available" ? "ok" : "warning"}
                  />
                </td>
                <td className="text-muted">{row.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <EmptyState
        title="Coming in Phase 3"
        description="Adapter wiring, credential vaulting, and model picker controls will land with the provider workstream. No Phase 3 adapters are started in this change."
      />
    </AdminShell>
  );
}
