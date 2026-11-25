import { useQuery } from "@tanstack/react-query";
import { Navigate } from "react-router-dom";
import { AdminShell } from "@/components/AdminShell";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";
import { StatusPill } from "@/components/ui/StatusPill";
import { useAuth } from "@/hooks/useAuth";
import { listUsers } from "@/lib/api";
import { canManageUsers } from "@/lib/auth";

export function AdminUsersPage() {
  const { token, user, isLoading } = useAuth();

  const query = useQuery({
    queryKey: ["admin-users", token],
    queryFn: () => listUsers(token!),
    enabled: Boolean(token) && canManageUsers(user),
  });

  if (!isLoading && user && !canManageUsers(user)) {
    return <Navigate to="/admin" replace />;
  }

  const users = query.data?.users ?? [];

  return (
    <AdminShell
      title="Users & roles"
      description="Local accounts from the API. Role edits and invites stay out of scope until a later phase."
    >
      {query.isLoading ? <LoadingState label="Loading users…" /> : null}
      {query.isError ? (
        <EmptyState title="Could not load users" description={(query.error as Error).message} />
      ) : null}
      {!query.isLoading && !query.isError && users.length === 0 ? (
        <EmptyState
          title="No users returned"
          description="The users API returned an empty list. Bootstrap admin should appear after API seed."
        />
      ) : null}
      {users.length ? (
        <div className="df-panel overflow-x-auto">
          <table className="df-table">
            <thead>
              <tr>
                <th>Email</th>
                <th>Name</th>
                <th>Role</th>
                <th>Active</th>
              </tr>
            </thead>
            <tbody>
              {users.map((row) => (
                <tr key={row.id}>
                  <td className="font-medium">{row.email}</td>
                  <td className="text-muted">{row.full_name ?? "—"}</td>
                  <td>
                    <StatusPill label={row.role} />
                  </td>
                  <td>
                    <StatusPill
                      label={row.is_active ? "active" : "inactive"}
                      tone={row.is_active ? "ok" : "inactive"}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </AdminShell>
  );
}
