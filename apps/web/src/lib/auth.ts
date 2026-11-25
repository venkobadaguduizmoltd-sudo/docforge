import type { User } from "@/lib/api";

export const TOKEN_KEY = "docforge-token";

export type RoleName = "admin" | "template-editor" | "editor" | "viewer";

const ROLE_RANK: Record<RoleName, number> = {
  viewer: 10,
  editor: 20,
  "template-editor": 30,
  admin: 100,
};

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}

export function parseRole(role: string | null | undefined): RoleName | null {
  if (!role) return null;
  if (role in ROLE_RANK) return role as RoleName;
  return null;
}

export function roleAtLeast(userRole: string | null | undefined, minimum: RoleName): boolean {
  const parsed = parseRole(userRole);
  if (!parsed) return false;
  return ROLE_RANK[parsed] >= ROLE_RANK[minimum];
}

/** Admin shell: template-editor and admin (Phases 3–4 own deep UIs). */
export function canAccessAdmin(user: User | null | undefined): boolean {
  return roleAtLeast(user?.role, "template-editor");
}

export function canManageUsers(user: User | null | undefined): boolean {
  return roleAtLeast(user?.role, "admin");
}

export function canManageSettings(user: User | null | undefined): boolean {
  return roleAtLeast(user?.role, "admin");
}
