import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { AppShell } from "@/components/AppShell";
import { login } from "@/lib/api";

const TOKEN_KEY = "docforge-token";

export function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("admin@localhost");
  const [password, setPassword] = useState("");
  const mutation = useMutation({
    mutationFn: () => login(email, password),
    onSuccess: (data) => {
      window.localStorage.setItem(TOKEN_KEY, data.access_token);
      navigate("/");
    },
  });

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    mutation.mutate();
  };

  return (
    <AppShell title="DocForge">
      <section className="mx-auto max-w-md">
        <h2 className="mb-2 text-3xl font-semibold tracking-tight">Sign in</h2>
        <p className="mb-8 text-muted">Local JWT auth skeleton for Phase 0.</p>
        <form onSubmit={onSubmit} className="space-y-4">
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Email</span>
            <input
              className="w-full rounded-md border border-border bg-surface px-3 py-2 outline-none ring-accent focus:ring-2"
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
              className="w-full rounded-md border border-border bg-surface px-3 py-2 outline-none ring-accent focus:ring-2"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </label>
          {mutation.isError ? (
            <p className="text-sm text-red-600 dark:text-red-400" role="alert">
              Could not sign in. Check credentials and API availability.
            </p>
          ) : null}
          <button
            type="submit"
            disabled={mutation.isPending}
            className="w-full rounded-md bg-accent px-4 py-2.5 font-medium text-white transition hover:opacity-90 disabled:opacity-60 dark:text-canvas"
          >
            {mutation.isPending ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </section>
    </AppShell>
  );
}
