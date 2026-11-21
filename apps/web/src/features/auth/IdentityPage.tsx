import {
  ApiError,
  type CurrentUser,
  listIdentityLinks,
  listIdentityProviders,
  loadCsrfToken,
  logout,
  unlinkIdentity
} from "@openvietgis/client-sdk";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "../../app/api";
import {
  currentProtectedData,
  identityLinksKey,
  isAuthorizationLossStatus,
  protectedQueryOptions
} from "../../app/protected-query";
import { FreshAccount } from "./FreshAccount";
import "./account-page.css";

function IdentityDetails({ account }: { account: CurrentUser }) {
  const queryClient = useQueryClient();
  const linksKey = identityLinksKey(account.id);

  const links = useQuery({
    queryKey: linksKey,
    queryFn: () => listIdentityLinks(apiClient),
    ...protectedQueryOptions
  });
  const providers = useQuery({
    queryKey: ["identity-providers"],
    queryFn: () => listIdentityProviders(apiClient),
    ...protectedQueryOptions
  });

  const currentLinks = currentProtectedData(links);
  const currentProviders = currentProtectedData(providers);

  const unlink = useMutation({
    mutationFn: async (identityLinkId: string) => {
      await loadCsrfToken(apiClient);
      await unlinkIdentity(apiClient, identityLinkId);
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["me"] }),
        queryClient.invalidateQueries({ queryKey: linksKey })
      ]);
    },
    onError: async (error) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: linksKey }),
        ...(error instanceof ApiError &&
        isAuthorizationLossStatus(error.status)
          ? [queryClient.invalidateQueries({ queryKey: ["me"] })]
          : [])
      ]);
    }
  });

  const signOut = useMutation({
    mutationFn: async () => {
      await loadCsrfToken(apiClient);
      await logout(apiClient);
    },
    onSuccess: async () => {
      queryClient.clear();
      window.location.assign(import.meta.env.BASE_URL || "/");
    },
    onError: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["me"] }),
        queryClient.invalidateQueries({ queryKey: linksKey })
      ]);
    }
  });

  return (
    <main className="account-page">
      <header className="account-page-head">
        <span className="app-dashboard-kicker">TÀI KHOẢN</span>
        <h1>Tài khoản & phiên đăng nhập</h1>
        <p>Quản lý danh tính liên kết và phiên OpenVietGIS hiện tại.</p>
      </header>

      <div className="account-grid">
        <section className="account-card">
          <h2>Danh tính đã liên kết</h2>
          <p>Các danh tính có thể dùng để truy cập tài khoản OpenVietGIS này.</p>

          {links.fetchStatus !== "idle" || links.isPending ? (
            <p>Đang kiểm tra danh tính đã liên kết…</p>
          ) : !currentLinks ? (
            <p className="account-alert" role="alert">
              Không thể tải danh tính đã liên kết.
            </p>
          ) : null}

          <ul className="account-identity-list">
            {currentLinks?.map((link, index) => (
              <li key={link.id}>
                <div>
                  <strong>Danh tính {index + 1}</strong>
                  <small>Đang liên kết với tài khoản này</small>
                  <details className="account-technical">
                    <summary>Thông tin kỹ thuật</summary>
                    <code>{link.issuer}</code>
                    <code>{link.subject}</code>
                  </details>
                </div>
                {currentLinks.length > 1 ? (
                  <button
                    type="button"
                    disabled={unlink.isPending || signOut.isPending}
                    onClick={() => unlink.mutate(link.id)}
                  >
                    Hủy liên kết
                  </button>
                ) : null}
              </li>
            ))}
          </ul>

          <h2 style={{ marginTop: 22 }}>Liên kết thêm danh tính</h2>
          <p>Sử dụng một nhà cung cấp đã được cấu hình cho hệ thống.</p>

          {providers.fetchStatus !== "idle" || providers.isPending ? (
            <p>Đang kiểm tra nhà cung cấp danh tính…</p>
          ) : !currentProviders ? (
            <p className="account-alert" role="alert">
              Không thể tải nhà cung cấp danh tính.
            </p>
          ) : null}

          <div className="account-provider-list">
            {currentLinks &&
            !signOut.isPending &&
            !unlink.isPending &&
            currentProviders?.map((provider) => (
              <a
                className="account-provider-link"
                key={provider.id}
                href={
                  "/api/v1/auth/login/" +
                  encodeURIComponent(provider.id) +
                  "?mode=link&return_to=" +
                  encodeURIComponent("/app/account")
                }
              >
                Liên kết {provider.display_name}
              </a>
            ))}
          </div>
        </section>

        <aside className="account-card">
          <div className="account-profile">
            <strong>{account.display_name}</strong>
            {account.email_snapshot ? <span>{account.email_snapshot}</span> : null}
            <span>Trạng thái: đang hoạt động</span>
          </div>

          <h2>Phiên hiện tại</h2>
          <p>
            Đăng xuất sẽ kết thúc phiên OpenVietGIS trên trình duyệt này. Các
            quyền vẫn do máy chủ kiểm tra.
          </p>

          <button
            className="account-signout"
            type="button"
            onClick={() => signOut.mutate()}
            disabled={signOut.isPending || unlink.isPending}
          >
            {signOut.isPending ? "Đang đăng xuất…" : "Đăng xuất"}
          </button>

          {unlink.error ? (
            <p className="account-alert" role="alert">
              Không thể hủy liên kết danh tính.
            </p>
          ) : null}
          {signOut.error ? (
            <p className="account-alert" role="alert">
              Chưa xác định kết quả đăng xuất. Hệ thống đang kiểm tra lại phiên.
            </p>
          ) : null}
        </aside>
      </div>
    </main>
  );
}

export function IdentityPage() {
  return (
    <FreshAccount>
      {(account) => <IdentityDetails key={account.id} account={account} />}
    </FreshAccount>
  );
}
