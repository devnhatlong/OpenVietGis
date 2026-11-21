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
  const navigationCommands = buildNavigationItems(organizationId, projectId)
    .filter((item) => item.availability === "visible")
    .map((item) => ({
      id: "navigate-" + item.id,
      label: "Mở " + item.labelKey,
      keywords: item.labelKey.toLocaleLowerCase("vi"),
      destination: item.destination
    }));

  return [
    ...navigationCommands,
    {
      id: "navigate-account",
      label: "Mở Tài khoản & phiên đăng nhập",
      keywords: "tài khoản phiên đăng nhập identity session",
      destination: "/app/account"
    }
  ];
}
