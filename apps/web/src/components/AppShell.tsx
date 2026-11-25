import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { useDarkMode } from "@/hooks/useDarkMode";
import { canAccessAdmin } from "@/lib/auth";

type AppShellProps = {
  children: ReactNode;
  /** Wider main column for document workspace */
  wide?: boolean;
  bare?: boolean;
};

function BrandMark() {
  return (
    <Link to="/" className="group flex items-center gap-2.5">
      <span
        aria-hidden
        className="flex h-8 w-8 items-center justify-center rounded-md bg-ink text-sm font-semibold text-canvas transition group-hover:bg-accent"
      >
        Df
      </span>
      <span className="font-display text-xl font-semibold tracking-tight text-ink">DocForge</span>
    </Link>
  );
}

function UserMenu() {
  const { user, logout, token } = useAuth();
  const { isDark, toggle } = useDarkMode();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onPointer = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false);
    };
    window.addEventListener("mousedown", onPointer);
    return () => window.removeEventListener("mousedown", onPointer);
  }, []);

  if (!token) {
    return (
      <div className="flex items-center gap-2">
        <button type="button" className="df-btn-ghost" onClick={toggle} aria-label="Toggle theme">
          {isDark ? "Light" : "Dark"}
        </button>
        <Link to="/login" className="df-btn-primary">
          Sign in
        </Link>
      </div>
    );
  }

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        className="df-btn-secondary max-w-[14rem] truncate"
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={() => setOpen((value) => !value)}
      >
        {user?.email ?? "Account"}
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-40 mt-2 w-56 overflow-hidden rounded-lg border border-border bg-surface shadow-soft animate-fade-in"
        >
          <div className="border-b border-border px-3 py-2">
            <p className="truncate text-sm font-medium text-ink">{user?.email ?? "…"}</p>
            <p className="df-kicker mt-1">{user?.role ?? "session"}</p>
          </div>
          <button type="button" role="menuitem" className="df-btn-ghost w-full justify-start rounded-none" onClick={toggle}>
            Switch to {isDark ? "light" : "dark"}
          </button>
          <button
            type="button"
            role="menuitem"
            className="df-btn-ghost w-full justify-start rounded-none text-danger"
            onClick={() => {
              setOpen(false);
              logout();
            }}
          >
            Sign out
          </button>
        </div>
      ) : null}
    </div>
  );
}

export function AppShell({ children, wide = false, bare = false }: AppShellProps) {
  const { user } = useAuth();
  const location = useLocation();
  const showAdmin = canAccessAdmin(user);
  const maxWidth = wide ? "max-w-6xl" : "max-w-5xl";

  if (bare) {
    return <div className="min-h-screen">{children}</div>;
  }

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-border/80 bg-surface/85 backdrop-blur-md">
        <div className={`mx-auto flex ${maxWidth} items-center gap-6 px-4 py-3 sm:px-6`}>
          <BrandMark />
          <nav className="hidden flex-1 items-center gap-1 md:flex" aria-label="Primary">
            <NavLink to="/" end className="df-nav-link" aria-current={location.pathname === "/" ? "page" : undefined}>
              Docs
            </NavLink>
            <NavLink
              to="/generate"
              className="df-nav-link"
              aria-current={location.pathname.startsWith("/generate") ? "page" : undefined}
            >
              Generate
            </NavLink>
            {showAdmin ? (
              <NavLink
                to="/admin"
                className="df-nav-link"
                aria-current={location.pathname.startsWith("/admin") ? "page" : undefined}
              >
                Admin
              </NavLink>
            ) : null}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <nav className="flex items-center gap-1 md:hidden" aria-label="Mobile">
              <NavLink to="/" end className="df-nav-link">
                Docs
              </NavLink>
              <NavLink to="/generate" className="df-nav-link">
                Generate
              </NavLink>
              {showAdmin ? (
                <NavLink to="/admin" className="df-nav-link">
                  Admin
                </NavLink>
              ) : null}
            </nav>
            <UserMenu />
          </div>
        </div>
      </header>
      <main className={`mx-auto ${maxWidth} px-4 py-8 sm:px-6 sm:py-10`}>{children}</main>
    </div>
  );
}
