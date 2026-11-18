import { createBrowserRouter } from "react-router-dom";

import { IdentityPage } from "../features/auth/IdentityPage";
import { OrganizationHome } from "../features/organizations/OrganizationHome";
import { ProjectPage } from "../features/projects/ProjectPage";
import { MembershipPage } from "../features/membership/MembershipPage";
import { InvitationAcceptPage } from "../features/invitations/InvitationAcceptPage";
import { WorkspacePage } from "../features/workspaces/WorkspacePage";

import { SpatialCatalogPage } from "../features/spatial/SpatialCatalogPage";

export const router = createBrowserRouter([
  { path: "/", element: <OrganizationHome /> },
  { path: "/organizations/:organizationId", element: <OrganizationHome /> },
  { path: "/organizations/:organizationId/workspaces", element: <WorkspacePage /> },
  { path: "/organizations/:organizationId/projects", element: <ProjectPage /> },
  { path: "/organizations/:organizationId/projects/:projectId/spatial", element: <SpatialCatalogPage /> },
  { path: "/organizations/:organizationId/membership", element: <MembershipPage /> },
  { path: "/invitations/accept", element: <InvitationAcceptPage /> },
  { path: "/identity", element: <IdentityPage /> }
]);