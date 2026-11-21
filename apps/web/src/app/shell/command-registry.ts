import { buildNavigationItems } from "./navigation-model";

export interface ShellCommand {
  id: string;
  label: string;
  keywords: string;
  destination: string;
}

export function buildShellCommands(
  organizationId?: string,
  projectId?: string
): ShellCommand[] {
  return buildNavigationItems(organizationId, projectId)
    .filter((item) => item.availability === "visible")
    .map((item) => ({
      id: "navigate-" + item.id,
      label: "Mở " + item.labelKey,
      keywords: item.labelKey.toLocaleLowerCase("vi"),
      destination: item.destination
    }));
}
