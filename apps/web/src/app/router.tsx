import {
  Navigate,
  Outlet,
  createBrowserRouter,
  useParams
} from "react-router-dom";

import {
  legacyOrganizationDestination,
  legacyProjectDestination,
  staticLegacyRouteDestinations
} from "./route-contract";
import { SessionBoundary } from "./session/SessionBoundary";
import { AppShell } from "./shell/AppShell";
import { IdentityPage } from "../features/auth/IdentityPage";
import { LoginPage } from "../features/auth/LoginPage";
import { AppDashboard } from "../features/dashboard/AppDashboard";
import { InvitationAcceptPage } from "../features/invitations/InvitationAcceptPage";
import { LandingPage } from "../features/landing/LandingPage";
import { MapWorkspace } from "../features/map/MapWorkspace";
import { MembershipPage } from "../features/membership/MembershipPage";
import { OrganizationHome } from "../features/organizations/OrganizationHome";
import { CartographyWorkbenchPage } from "../features/platform/CartographyWorkbenchPage";
import { EditingWorkbenchPage } from "../features/platform/EditingWorkbenchPage";
import { PlatformHubPage } from "../features/platform/PlatformHubPage";
import { ProcessingWorkbenchPage } from "../features/platform/ProcessingWorkbenchPage";
import { QueryWorkbenchPage } from "../features/platform/QueryWorkbenchPage";
import { FrontendPreviewPage } from "../features/preview/FrontendPreviewPage";
import { ProjectPage } from "../features/projects/ProjectPage";
import { SpatialCatalogPage } from "../features/spatial/SpatialCatalogPage";
import { ImportExportPage } from "../features/transfers/ImportExportPage";
import { WorkspacePage } from "../features/workspaces/WorkspacePage";

const routerBasename =
  window.location.pathname === "/dev" ||
  window.location.pathname.startsWith("/dev/")
    ? "/dev"
    : undefined;

function AuthenticatedLayout() {
  return (
    <SessionBoundary>
      <AppShell>
        <Outlet />
      </AppShell>
    </SessionBoundary>
  );
}

function LegacyOrganizationRedirect({ suffix = "" }: { suffix?: string }) {
  const { organizationId } = useParams();
  if (!organizationId) return <Navigate replace to="/app" />;

  return (
    <Navigate
      replace
      to={legacyOrganizationDestination(organizationId, suffix)}
    />
  );
}

function LegacyProjectRedirect({ suffix }: { suffix: string }) {
  const { organizationId, projectId } = useParams();
  if (!organizationId || !projectId) return <Navigate replace to="/app" />;

  return (
    <Navigate
      replace
      to={legacyProjectDestination(organizationId, projectId, suffix)}
    />
  );
}

const uxPreviewMode = import.meta.env.VITE_UX_PREVIEW === "true";

export const router = createBrowserRouter(
  [
    {
      path: "/",
      element: uxPreviewMode ? <FrontendPreviewPage /> : <LandingPage />
    },
    { path: "/landing", element: <LandingPage /> },
    { path: "/login", element: <LoginPage /> },

    {
      path: "/app",
      element: <AuthenticatedLayout />,
      children: [
        { index: true, element: <AppDashboard /> },
        {
          path: "organizations",
          element: <OrganizationHome />
        },
        {
          path: "organizations/:organizationId",
          element: <OrganizationHome />
        },
        {
          path: "organizations/:organizationId/workspaces",
          element: <WorkspacePage />
        },
        {
          path: "organizations/:organizationId/projects",
          element: <ProjectPage />
        },
        {
          path: "organizations/:organizationId/projects/:projectId/spatial",
          element: <SpatialCatalogPage />
        },
        {
          path: "organizations/:organizationId/projects/:projectId/map",
          element: <MapWorkspace />
        },
        {
          path: "organizations/:organizationId/projects/:projectId/transfers",
          element: <ImportExportPage />
        },
        {
          path: "organizations/:organizationId/projects/:projectId/editing",
          element: <EditingWorkbenchPage />
        },
        {
          path: "organizations/:organizationId/projects/:projectId/queries",
          element: <QueryWorkbenchPage />
        },
        {
          path: "organizations/:organizationId/projects/:projectId/processing",
          element: <ProcessingWorkbenchPage />
        },
        {
          path: "organizations/:organizationId/projects/:projectId/cartography",
          element: <CartographyWorkbenchPage />
        },
        {
          path: "organizations/:organizationId/projects/:projectId/platform-hub",
          element: <PlatformHubPage />
        },
        {
          path: "organizations/:organizationId/membership",
          element: <MembershipPage />
        },
        { path: "account", element: <IdentityPage /> },
        {
          path: "invitations/accept",
          element: <InvitationAcceptPage />
        }
      ]
    },

    {
      path: "/organizations/:organizationId",
      element: <LegacyOrganizationRedirect />
    },
    {
      path: "/organizations/:organizationId/workspaces",
      element: <LegacyOrganizationRedirect suffix="/workspaces" />
    },
    {
      path: "/organizations/:organizationId/projects",
      element: <LegacyOrganizationRedirect suffix="/projects" />
    },
    {
      path: "/organizations/:organizationId/projects/:projectId/spatial",
      element: <LegacyProjectRedirect suffix="/spatial" />
    },
    {
      path: "/organizations/:organizationId/projects/:projectId/map",
      element: <LegacyProjectRedirect suffix="/map" />
    },
    {
      path: "/organizations/:organizationId/projects/:projectId/transfers",
      element: <LegacyProjectRedirect suffix="/transfers" />
    },
    {
      path: "/organizations/:organizationId/projects/:projectId/editing",
      element: <LegacyProjectRedirect suffix="/editing" />
    },
    {
      path: "/organizations/:organizationId/projects/:projectId/queries",
      element: <LegacyProjectRedirect suffix="/queries" />
    },
    {
      path: "/organizations/:organizationId/projects/:projectId/processing",
      element: <LegacyProjectRedirect suffix="/processing" />
    },
    {
      path: "/organizations/:organizationId/projects/:projectId/cartography",
      element: <LegacyProjectRedirect suffix="/cartography" />
    },
    {
      path: "/organizations/:organizationId/projects/:projectId/platform-hub",
      element: <LegacyProjectRedirect suffix="/platform-hub" />
    },
    {
      path: "/organizations/:organizationId/membership",
      element: <LegacyOrganizationRedirect suffix="/membership" />
    },
    {
      path: "/identity",
      element: (
        <Navigate
          replace
          to={staticLegacyRouteDestinations["/identity"] ?? "/app/account"}
        />
      )
    },
    {
      path: "/invitations/accept",
      element: (
        <Navigate
          replace
          to={
            staticLegacyRouteDestinations["/invitations/accept"] ??
            "/app/invitations/accept"
          }
        />
      )
    }
  ],
  routerBasename ? { basename: routerBasename } : {}
);
