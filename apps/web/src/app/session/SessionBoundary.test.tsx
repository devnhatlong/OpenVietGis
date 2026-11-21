import { ApiError } from "@openvietgis/client-sdk";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const useQueryMock = vi.fn();
const removeQueriesMock = vi.fn();

vi.mock("@tanstack/react-query", () => ({
  useQuery: (options: unknown) => useQueryMock(options),
  useQueryClient: () => ({ removeQueries: removeQueriesMock })
}));

vi.mock("react-router-dom", () => ({
  Navigate: ({ to }: { to: string }) => <span data-navigate={to}>redirect</span>,
  useLocation: () => ({ pathname: "/app/projects" })
}));

import { SessionBoundary } from "./SessionBoundary";

const account = {
  id: "user-1",
  display_name: "Owner Alpha",
  email_snapshot: "owner@example.test",
  status: "active" as const
};

describe("SessionBoundary", () => {
  beforeEach(() => {
    useQueryMock.mockReset();
    removeQueriesMock.mockReset();
  });

  it("keeps authenticated shell content mounted during background /me revalidation", () => {
    useQueryMock.mockReturnValue({
      data: account,
      error: null,
      fetchStatus: "fetching",
      isPending: false
    });

    const html = renderToStaticMarkup(
      <SessionBoundary>
        <div data-testid="protected-shell">Protected shell</div>
      </SessionBoundary>
    );

    expect(html).toContain("Protected shell");
    expect(html).not.toContain("Đang mở không gian làm việc");
  });

  it("redirects to login with a return destination after confirmed 401", () => {
    useQueryMock.mockReturnValue({
      data: undefined,
      error: new ApiError(
        401,
        new Response(null, { status: 401 })
      ),
      fetchStatus: "idle",
      isPending: false
    });

    const html = renderToStaticMarkup(
      <SessionBoundary>
        <div>Protected shell</div>
      </SessionBoundary>
    );

    expect(html).not.toContain("Protected shell");
    expect(html).toContain("/login?return_to=");
  });
});
