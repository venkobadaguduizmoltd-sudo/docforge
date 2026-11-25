import { describe, expect, it } from "vitest";
import {
  canAccessAdmin,
  canManageProviders,
  canManageSettings,
  canManageUsers,
  roleAtLeast,
} from "@/lib/auth";

describe("RBAC helpers", () => {
  it("ranks roles for admin shell access", () => {
    expect(canAccessAdmin({ role: "admin" } as never)).toBe(true);
    expect(canAccessAdmin({ role: "template-editor" } as never)).toBe(true);
    expect(canAccessAdmin({ role: "editor" } as never)).toBe(false);
    expect(canAccessAdmin({ role: "viewer" } as never)).toBe(false);
  });

  it("gates users and settings to admin only", () => {
    expect(canManageUsers({ role: "admin" } as never)).toBe(true);
    expect(canManageUsers({ role: "template-editor" } as never)).toBe(false);
    expect(canManageSettings({ role: "template-editor" } as never)).toBe(false);
    expect(canManageSettings({ role: "admin" } as never)).toBe(true);
    expect(canManageProviders({ role: "admin" } as never)).toBe(true);
    expect(canManageProviders({ role: "template-editor" } as never)).toBe(false);
  });

  it("compares role hierarchy", () => {
    expect(roleAtLeast("editor", "viewer")).toBe(true);
    expect(roleAtLeast("viewer", "editor")).toBe(false);
    expect(roleAtLeast("unknown", "viewer")).toBe(false);
  });
});
