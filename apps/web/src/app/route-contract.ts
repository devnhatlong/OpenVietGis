export function canonicalOrganizationPath(organizationId: string): string {
  return "/app/organizations/" + encodeURIComponent(organizationId);
}

export function canonicalProjectPath(
  organizationId: string,
  projectId: string
): string {
  return (
    canonicalOrganizationPath(organizationId) +
    "/projects/" +
    encodeURIComponent(projectId)
  );
}

export function legacyOrganizationDestination(
  organizationId: string,
  suffix = ""
): string {
  return canonicalOrganizationPath(organizationId) + suffix;
}

export function legacyProjectDestination(
  organizationId: string,
  projectId: string,
  suffix: string
): string {
  return canonicalProjectPath(organizationId, projectId) + suffix;
}

export const staticLegacyRouteDestinations: Readonly<Record<string, string>> = {
  "/identity": "/app/account",
  "/invitations/accept": "/app/invitations/accept"
};
