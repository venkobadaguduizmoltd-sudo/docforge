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
