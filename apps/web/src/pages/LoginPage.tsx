import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { AppShell } from "@/components/AppShell";
import { useAuth } from "@/hooks/useAuth";
import { useDarkMode } from "@/hooks/useDarkMode";
import { login } from "@/lib/api";

export function LoginPage() {
  const { loginSuccess, token } = useAuth();
  const { isDark, toggle } = useDarkMode();
  const [email, setEmail] = useState("admin@localhost");
  const [password, setPassword] = useState("");
  const mutation = useMutation({
    mutationFn: () => login(email, password),
    onSuccess: (data) => loginSuccess(data.access_token, "/"),
  });

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    mutation.mutate();
  };

  return (
    <AppShell bare>
      <div className="relative flex min-h-screen flex-col">
        <div className="absolute inset-0 -z-10 bg-[radial-gradient(800px_420px_at_15%_0%,rgb(var(--color-accent)/0.12),transparent_60%),linear-gradient(165deg,rgb(var(--color-surface)),rgb(var(--color-canvas)))]" />
        <header className="flex items-center justify-between px-6 py-5">
          <Link to="/" className="font-display text-xl font-semibold tracking-tight text-ink">
            DocForge
          </Link>
          <button type="button" className="df-btn-ghost" onClick={toggle} aria-label="Toggle theme">
            {isDark ? "Light" : "Dark"}
          </button>
        </header>
        <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-6 pb-16">
          <div className="animate-fade-up">
            <p className="df-kicker mb-3">Sign in</p>
            <h1 className="font-display text-4xl font-semibold tracking-tight text-ink">
              Welcome back
            </h1>
            <p className="mt-3 text-muted">
              Local JWT auth. Demo: <span className="font-mono text-sm">admin@localhost</span>
            </p>
          </div>
          {token ? (
            <p className="mt-6 text-sm text-muted">
              Already signed in.{" "}
              <Link className="font-medium text-accent underline" to="/">
                Go to workspace
              </Link>
            </p>
          ) : null}
          <form onSubmit={onSubmit} className="df-panel mt-8 space-y-4 p-6 animate-fade-in">
            <label className="block space-y-1.5 text-sm">
              <span className="text-muted">Email</span>
              <input
                className="df-input"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="username"
              />
            </label>
            <label className="block space-y-1.5 text-sm">
              <span className="text-muted">Password</span>
              <input
                className="df-input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </label>
            {mutation.isError ? (
              <p className="text-sm text-danger" role="alert">
                Could not sign in. Check credentials and API availability.
              </p>
            ) : null}
            <button type="submit" disabled={mutation.isPending} className="df-btn-primary w-full">
              {mutation.isPending ? "Signing in…" : "Sign in"}
            </button>
          </form>
        </main>
      </div>
    </AppShell>
  );
}
