export type WorkspaceResponsiveMode = "desktop" | "tablet" | "mobile";

export function getWorkspaceResponsiveMode(width: number): WorkspaceResponsiveMode {
  if (!Number.isFinite(width) || width < 768) return "mobile";
  if (width < 1280) return "tablet";
  return "desktop";
}
