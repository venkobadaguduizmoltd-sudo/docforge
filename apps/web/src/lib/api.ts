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

export type Citation = {
  file: string;
  line?: number | null;
  end_line?: number | null;
  commit_sha?: string | null;
  symbol?: string | null;
};

export type DocumentSection = {
  section_id: string;
  content_json: Record<string, unknown>;
  is_locked: boolean;
  citations: Citation[];
  pending_suggestion: {
    proposed?: Record<string, unknown>;
    current?: Record<string, unknown>;
    prompt?: string | null;
  } | null;
  updated_at: string;
};

export type DocForgeDocument = {
  id: string;
  title: string;
  status: string;
  source_job_id: string | null;
  template_slug: string;
  template_sha256: string | null;
  pinned_commit_sha: string | null;
  sections: DocumentSection[];
  current_revision: number;
  created_at: string;
  updated_at: string;
};

export type Revision = {
  revision_number: number;
  note: string | null;
  created_at: string;
};

async function authJson<T>(token: string, path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function materializeDocument(token: string, jobId: string): Promise<DocForgeDocument> {
  return authJson(token, `/documents/from-job/${jobId}`, { method: "POST" });
}

export function fetchDocument(token: string, documentId: string): Promise<DocForgeDocument> {
  return authJson(token, `/documents/${documentId}`);
}

export function editSection(
  token: string,
  documentId: string,
  sectionId: string,
  content: Record<string, unknown>,
): Promise<DocForgeDocument> {
  return authJson(token, `/documents/${documentId}/sections/${sectionId}`, {
    method: "PUT",
    body: JSON.stringify({ content }),
  });
}

export function regenerateSection(
  token: string,
  documentId: string,
  sectionId: string,
  prompt?: string,
): Promise<DocForgeDocument> {
  return authJson(token, `/documents/${documentId}/sections/${sectionId}/regenerate`, {
    method: "POST",
    body: JSON.stringify({ prompt: prompt || null }),
  });
}

export function regenerateAllUnlocked(
  token: string,
  documentId: string,
  prompt?: string,
): Promise<DocForgeDocument> {
  return authJson(token, `/documents/${documentId}/regenerate`, {
    method: "POST",
    body: JSON.stringify({ prompt: prompt || null }),
  });
}

export function suggestSection(
  token: string,
  documentId: string,
  sectionId: string,
  prompt?: string,
): Promise<DocForgeDocument> {
  return authJson(token, `/documents/${documentId}/sections/${sectionId}/suggest`, {
    method: "POST",
    body: JSON.stringify({ prompt: prompt || null }),
  });
}

export function acceptSuggestion(
  token: string,
  documentId: string,
  sectionId: string,
): Promise<DocForgeDocument> {
  return authJson(token, `/documents/${documentId}/sections/${sectionId}/suggestions/accept`, {
    method: "POST",
  });
}

export function rejectSuggestion(
  token: string,
  documentId: string,
  sectionId: string,
): Promise<DocForgeDocument> {
  return authJson(token, `/documents/${documentId}/sections/${sectionId}/suggestions/reject`, {
    method: "POST",
  });
}

export function lockSection(
  token: string,
  documentId: string,
  sectionId: string,
): Promise<DocForgeDocument> {
  return authJson(token, `/documents/${documentId}/sections/${sectionId}/lock`, { method: "POST" });
}

export function unlockSection(
  token: string,
  documentId: string,
  sectionId: string,
): Promise<DocForgeDocument> {
  return authJson(token, `/documents/${documentId}/sections/${sectionId}/unlock`, {
    method: "POST",
  });
}

export function fetchVersions(token: string, documentId: string): Promise<Revision[]> {
  return authJson(token, `/documents/${documentId}/versions`);
}

export function undoDocument(token: string, documentId: string): Promise<DocForgeDocument> {
  return authJson(token, `/documents/${documentId}/undo`, { method: "POST" });
}

export function restoreVersion(
  token: string,
  documentId: string,
  revisionNumber: number,
): Promise<DocForgeDocument> {
  return authJson(token, `/documents/${documentId}/versions/${revisionNumber}/restore`, {
    method: "POST",
  });
}

export type BuiltinTemplate = {
  slug: string;
  name?: string | null;
  sha256: string;
  immutable: boolean;
};

export function listDocuments(token: string): Promise<DocForgeDocument[]> {
  return authJson(token, "/documents");
}

export function listBuiltinTemplates(token: string): Promise<{ templates: BuiltinTemplate[] }> {
  return authJson(token, "/templates/builtin");
}

export function listJobs(token: string): Promise<{ jobs: Job[] }> {
  return authJson(token, "/jobs");
}

export function listUsers(token: string): Promise<{ users: User[] }> {
  return authJson(token, "/admin/users");
}

export type AdminSettings = {
  retention_days: number;
  feature_flags: Record<string, boolean>;
  note: string;
};

export function fetchAdminSettings(token: string): Promise<AdminSettings> {
  return authJson(token, "/admin/settings");
}
