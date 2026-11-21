import type { ReactElement } from "react";
import {
  Navigate,
  createBrowserRouter,
  useParams
} from "react-router-dom";

import { SessionBoundary } from "./session/SessionBoundary";
import { AppShell } from "./shell/AppShell";
import { LandingPage } from "../features/landing/LandingPage";
import { LoginPage } from "../features/auth/LoginPage";
import { IdentityPage } from "../features/auth/IdentityPage";
import { OrganizationHome } from "../features/organizations/OrganizationHome";
import { ProjectPage } from "../features/projects/ProjectPage";
import { MembershipPage } from "../features/membership/MembershipPage";
import { InvitationAcceptPage } from "../features/invitations/InvitationAcceptPage";
import { WorkspacePage } from "../features/workspaces/WorkspacePage";
import { SpatialCatalogPage } from "../features/spatial/SpatialCatalogPage";
import { MapWorkspace } from "../features/map/MapWorkspace";
import { ImportExportPage } from "../features/transfers/ImportExportPage";
import { EditingWorkbenchPage } from "../features/platform/EditingWorkbenchPage";
import { QueryWorkbenchPage } from "../features/platform/QueryWorkbenchPage";
import { ProcessingWorkbenchPage } from "../features/platform/ProcessingWorkbenchPage";
import { CartographyWorkbenchPage } from "../features/platform/CartographyWorkbenchPage";
import { PlatformHubPage } from "../features/platform/PlatformHubPage";

const routerBasename =
  window.location.pathname === "/dev" ||
  window.location.pathname.startsWith("/dev/")
    ? "/dev"
    : undefined;

function protectedElement(element: ReactElement) {
  return (
    <SessionBoundary>
      <AppShell>{element}</AppShell>
    </SessionBoundary>
  );
}

function LegacyOrganizationRedirect({ suffix = "" }: { suffix?: string }) {
  const { organizationId } = useParams();
  if (!organizationId) return <Navigate replace to="/app" />;
  return (
    <Navigate
      replace
      to={"/app/organizations/" + encodeURIComponent(organizationId) + suffix}
    />
  );
}

function LegacyProjectRedirect({ suffix }: { suffix: string }) {
  const { organizationId, projectId } = useParams();
  if (!organizationId || !projectId) return <Navigate replace to="/app" />;
  return (
    <Navigate
      replace
      to={
        "/app/organizations/" +
        encodeURIComponent(organizationId) +
        "/projects/" +
        encodeURIComponent(projectId) +
        suffix
      }
    />
  );
}

export const router = createBrowserRouter(
  [
    { path: "/", element: <LandingPage /> },
    { path: "/login", element: <LoginPage /> },

    { path: "/app", element: protectedElement(<OrganizationHome />) },
    {
      path: "/app/organizations/:organizationId",
      element: protectedElement(<OrganizationHome />)
    },
    {
      path: "/app/organizations/:organizationId/workspaces",
      element: protectedElement(<WorkspacePage />)
    },
    {
      path: "/app/organizations/:organizationId/projects",
      element: protectedElement(<ProjectPage />)
    },
    {
      path: "/app/organizations/:organizationId/projects/:projectId/spatial",
      element: protectedElement(<SpatialCatalogPage />)
    },
    {
      path: "/app/organizations/:organizationId/projects/:projectId/map",
      element: protectedElement(<MapWorkspace />)
    },
    {
      path: "/app/organizations/:organizationId/projects/:projectId/transfers",
      element: protectedElement(<ImportExportPage />)
    },
    {
      path: "/app/organizations/:organizationId/projects/:projectId/editing",
      element: protectedElement(<EditingWorkbenchPage />)
    },
    {
      path: "/app/organizations/:organizationId/projects/:projectId/queries",
      element: protectedElement(<QueryWorkbenchPage />)
    },
    {
      path: "/app/organizations/:organizationId/projects/:projectId/processing",
      element: protectedElement(<ProcessingWorkbenchPage />)
    },
    {
      path: "/app/organizations/:organizationId/projects/:projectId/cartography",
      element: protectedElement(<CartographyWorkbenchPage />)
    },
    {
      path: "/app/organizations/:organizationId/projects/:projectId/platform-hub",
      element: protectedElement(<PlatformHubPage />)
    },
    {
      path: "/app/organizations/:organizationId/membership",
      element: protectedElement(<MembershipPage />)
    },
    { path: "/app/account", element: protectedElement(<IdentityPage />) },
    {
      path: "/app/invitations/accept",
      element: protectedElement(<InvitationAcceptPage />)
    },

    {
      path: "/app/organizations/:organizationId",
      element: <LegacyOrganizationRedirect />
    },
    {
      path: "/app/organizations/:organizationId/workspaces",
      element: <LegacyOrganizationRedirect suffix="/workspaces" />
    },
    {
      path: "/app/organizations/:organizationId/projects",
      element: <LegacyOrganizationRedirect suffix="/projects" />
    },
    {
      path: "/app/organizations/:organizationId/projects/:projectId/spatial",
      element: <LegacyProjectRedirect suffix="/spatial" />
    },
    {
      path: "/app/organizations/:organizationId/projects/:projectId/map",
      element: <LegacyProjectRedirect suffix="/map" />
    },
    {
      path: "/app/organizations/:organizationId/projects/:projectId/transfers",
      element: <LegacyProjectRedirect suffix="/transfers" />
    },
    {
      path: "/app/organizations/:organizationId/projects/:projectId/editing",
      element: <LegacyProjectRedirect suffix="/editing" />
    },
    {
      path: "/app/organizations/:organizationId/projects/:projectId/queries",
      element: <LegacyProjectRedirect suffix="/queries" />
    },
    {
      path: "/app/organizations/:organizationId/projects/:projectId/processing",
      element: <LegacyProjectRedirect suffix="/processing" />
    },
    {
      path: "/app/organizations/:organizationId/projects/:projectId/cartography",
      element: <LegacyProjectRedirect suffix="/cartography" />
    },
    {
      path: "/app/organizations/:organizationId/projects/:projectId/platform-hub",
      element: <LegacyProjectRedirect suffix="/platform-hub" />
    },
    {
      path: "/app/organizations/:organizationId/membership",
      element: <LegacyOrganizationRedirect suffix="/membership" />
    },
    { path: "/identity", element: <Navigate replace to="/app/account" /> },
    {
      path: "/invitations/accept",
      element: <Navigate replace to="/app/invitations/accept" />
    }
  ],
  routerBasename ? { basename: routerBasename } : {}
);
