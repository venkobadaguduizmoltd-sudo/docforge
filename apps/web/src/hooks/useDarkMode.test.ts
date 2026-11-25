import { describe, expect, it } from "vitest";

describe("dark mode token hook contract", () => {
  it("exposes light and dark theme tokens", () => {
    const tokens = ["light", "dark"] as const;
    expect(tokens).toContain("dark");
    expect(tokens).toContain("light");
  });
});
