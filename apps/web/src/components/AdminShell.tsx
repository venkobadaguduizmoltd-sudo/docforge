import type { ReactNode } from "react";
import { NavLink, Navigate } from "react-router-dom";
import { AppShell } from "@/components/AppShell";
import { LoadingState } from "@/components/ui/LoadingState";
import { useAuth } from "@/hooks/useAuth";
import { canAccessAdmin, canManageSettings, canManageUsers } from "@/lib/auth";

type AdminShellProps = {
  children: ReactNode;
  title: string;
  description?: string;
};

const LINKS: { to: string; label: string; end?: boolean; adminOnly?: boolean }[] = [
  { to: "/admin", label: "Overview", end: true },
  { to: "/admin/templates", label: "Templates" },
  { to: "/admin/providers", label: "AI Providers" },
  { to: "/admin/users", label: "Users & roles", adminOnly: true },
  { to: "/admin/jobs", label: "Jobs" },
  { to: "/admin/settings", label: "Settings", adminOnly: true },
];

export function AdminShell({ children, title, description }: AdminShellProps) {
  const { token, user, isLoading } = useAuth();

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  if (isLoading) {
    return (
      <AppShell wide>
        <LoadingState label="Checking session…" />
      </AppShell>
    );
  }

  if (!canAccessAdmin(user)) {
    return (
      <AppShell>
        <div className="df-panel p-8">
          <h1 className="df-title text-2xl">Admin access required</h1>
          <p className="df-subtitle">
            The admin shell is available to <code className="font-mono text-sm">admin</code> and{" "}
            <code className="font-mono text-sm">template-editor</code> roles. Deep template and
            provider UIs land in Phases 4 and 3.
          </p>
        </div>
      </AppShell>
    );
  }

  const links = LINKS.filter((link) => {
    if (!link.adminOnly) return true;
    if (link.to === "/admin/users") return canManageUsers(user);
    if (link.to === "/admin/settings") return canManageSettings(user);
    return true;
  });

  return (
    <AppShell wide>
      <div className="grid gap-8 lg:grid-cols-[220px_1fr]">
        <aside className="space-y-4">
          <div>
            <p className="df-kicker">Administration</p>
            <p className="mt-1 font-display text-lg font-semibold text-ink">Control plane</p>
          </div>
          <nav className="space-y-1" aria-label="Admin">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.end}
                className={({ isActive }) =>
                  isActive ? "df-admin-link bg-accent-soft text-ink" : "df-admin-link"
                }
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
        </aside>
        <section className="min-w-0 space-y-6">
          <div className="animate-fade-up">
            <p className="df-kicker mb-2">Admin</p>
            <h1 className="df-title text-3xl sm:text-4xl">{title}</h1>
            {description ? <p className="df-subtitle">{description}</p> : null}
          </div>
          {children}
        </section>
      </div>
    </AppShell>
  );
}
