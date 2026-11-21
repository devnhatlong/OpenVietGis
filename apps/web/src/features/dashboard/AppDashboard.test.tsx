import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const useQueryMock = vi.fn();
const useQueriesMock = vi.fn();

vi.mock("@tanstack/react-query", () => ({
  useQuery: (options: unknown) => useQueryMock(options),
  useQueries: (options: unknown) => useQueriesMock(options)
}));

vi.mock("../../app/session/SessionBoundary", () => ({
  useSession: () => ({
    account: {
      id: "user-1",
      display_name: "Owner Alpha",
      email_snapshot: "owner@example.test",
      status: "active"
    },
    checking: false,
    networkWarning: false
  })
}));

vi.mock("react-router-dom", () => ({
  Link: ({
    children,
    to
  }: {
    children: unknown;
    to: string;
  }) => <a href={to}>{children as string}</a>
}));

import { AppDashboard } from "./AppDashboard";

function success<T>(data: T) {
  return {
    data,
    error: null,
    fetchStatus: "idle" as const,
    isPending: false,
    isSuccess: true
  };
}

describe("AppDashboard", () => {
  beforeEach(() => {
    useQueryMock.mockReset();
    useQueriesMock.mockReset();
  });

  it("renders human-readable organization and project cards without primary UUID labels", () => {
    useQueryMock.mockImplementation((options: { queryKey: unknown[] }) =>
      options.queryKey[0] === "bootstrap-status"
        ? success({ initialized: true })
        : success([
            {
              id: "dccf019f-d2dc-4b8e-83f7-e3603080aa4c",
              name: "Tổ chức GIS",
              slug: "to-chuc-gis",
              role: "owner",
              status: "active"
            }
          ])
    );
    useQueriesMock.mockReturnValue([
      success([
        {
          id: "d38b5ebc-f78d-4e06-9e0f-4d0a31fd98bc",
          organization_id: "dccf019f-d2dc-4b8e-83f7-e3603080aa4c",
          workspace_id: null,
          name: "Dự án Bản đồ Hà Nội",
          slug: "ha-noi",
          status: "active"
        }
      ])
    ]);

    const html = renderToStaticMarkup(<AppDashboard />);
    expect(html).toContain("Dự án Bản đồ Hà Nội");
    expect(html).toContain("Tổ chức GIS");
    expect(html).not.toContain("Mã tổ chức");
    expect(html).not.toContain("Mã dự án");
    expect(html).toContain(">Tổ chức GIS<");
    expect(html).toContain(">Dự án Bản đồ Hà Nội<");
  });

  it("renders bootstrap gate for an uninitialized installation", () => {
    useQueryMock.mockImplementation((options: { queryKey: unknown[] }) =>
      options.queryKey[0] === "bootstrap-status"
        ? success({ initialized: false })
        : success([])
    );
    useQueriesMock.mockReturnValue([]);

    const html = renderToStaticMarkup(<AppDashboard />);
    expect(html).toContain("Khởi tạo hệ thống OpenVietGIS");
    expect(html).not.toContain("Chào Owner Alpha");
  });

  it("renders a useful no-project empty state", () => {
    useQueryMock.mockImplementation((options: { queryKey: unknown[] }) =>
      options.queryKey[0] === "bootstrap-status"
        ? success({ initialized: true })
        : success([
            {
              id: "org-1",
              name: "Tổ chức GIS",
              slug: "to-chuc-gis",
              role: "member"
            }
          ])
    );
    useQueriesMock.mockReturnValue([success([])]);

    const html = renderToStaticMarkup(<AppDashboard />);
    expect(html).toContain("Chưa có dự án khả dụng");
    expect(html).toContain("Chọn một tổ chức để tạo dự án");
  });
});
