/** Shared constants and types for DocForge (thin Phase 0 package). */

export const ROLES = ["admin", "template-editor", "editor", "viewer"] as const;
export type Role = (typeof ROLES)[number];

export type SectionContent = {
  sectionId: string;
  content: Record<string, unknown>;
};

export type TemplateSpecStub = {
  version: number;
  sections: Array<{ id: string; title: string }>;
};
