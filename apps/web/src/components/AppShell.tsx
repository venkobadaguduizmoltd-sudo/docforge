import type { ReactNode } from "react";
import { useDarkMode } from "@/hooks/useDarkMode";

type AppShellProps = {
  children: ReactNode;
  title?: string;
};

export function AppShell({ children, title = "DocForge" }: AppShellProps) {
  const { isDark, toggle } = useDarkMode();

  return (
    <div className="min-h-screen">
      <header className="border-b border-border/80 bg-surface/80 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-muted">Documentation platform</p>
            <h1 className="text-xl font-semibold tracking-tight text-ink">{title}</h1>
          </div>
          <button
            type="button"
            onClick={toggle}
            className="rounded-md border border-border bg-canvas px-3 py-1.5 text-sm text-ink transition hover:border-accent"
            aria-label="Toggle dark mode"
          >
            {isDark ? "Light" : "Dark"}
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-10">{children}</main>
    </div>
  );
}
