const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export type TokenResponse = {
  access_token: string;
  token_type: string;
};

export type User = {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  is_active: boolean;
};

export type Job = {
  id: string;
  job_type: string;
  status: string;
  payload: Record<string, unknown>;
  result: {
    artifacts?: { html?: string; docx?: string; pdf?: string };
    commit_sha?: string;
  } | null;
  error: string | null;
  commit_sha: string | null;
  created_at: string;
  updated_at: string;
};

export async function login(email: string, password: string): Promise<TokenResponse> {
  const response = await fetch(`${API_URL}/auth/login/json`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    throw new Error("Login failed");
  }
  return response.json() as Promise<TokenResponse>;
}

export async function fetchMe(token: string): Promise<User> {
  const response = await fetch(`${API_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error("Session invalid");
  }
  return response.json() as Promise<User>;
}

export async function fetchHealth(): Promise<{ status: string }> {
  const response = await fetch(`${API_URL}/health`);
  if (!response.ok) {
    throw new Error("API unreachable");
  }
  return response.json() as Promise<{ status: string }>;
}

export async function startGenerateJob(
  token: string,
  body: {
    provider: string;
    full_name: string;
    ref: string;
    template_slug: string;
  },
): Promise<Job> {
  const response = await fetch(`${API_URL}/jobs/generate`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error("Failed to start job");
  }
  return response.json() as Promise<Job>;
}

export async function fetchJob(token: string, jobId: string): Promise<Job> {
  const response = await fetch(`${API_URL}/jobs/${jobId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error("Job not found");
  }
  return response.json() as Promise<Job>;
}

export function jobEventsUrl(jobId: string, token: string): string {
  const url = new URL(`${API_URL}/jobs/${jobId}/events`);
  url.searchParams.set("access_token", token);
  return url.toString();
}
