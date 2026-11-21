import {
  listIdentityProviders,
  type IdentityProviderSummary
} from "@openvietgis/client-sdk";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { apiClient } from "../../app/api";
import { safeReturnTo } from "../../app/session/return-destination";
import "./auth.css";

function loginUrl(provider: IdentityProviderSummary, returnTo: string): string {
  return (
    "/api/v1/auth/login/" +
    encodeURIComponent(provider.id) +
    "?return_to=" +
    encodeURIComponent(returnTo)
  );
}

export function LoginPage() {
  const [searchParams] = useSearchParams();
  const returnTo = safeReturnTo(searchParams.get("return_to"));
  const providers = useQuery({
    queryKey: ["identity-providers"],
    queryFn: () => listIdentityProviders(apiClient)
  });

  return (
    <main className="ovg-login-page">
      <a className="ovg-skip-link" href="#login-card">Bỏ qua điều hướng</a>
      <header className="ovg-login-page-header">
        <Link className="ovg-brand" to="/">
          <span className="ovg-brand-mark">OVG</span>
          <span><strong>OpenVietGIS</strong><small>Nền tảng GIS web</small></span>
        </Link>
        <Link className="ovg-back-link" to="/">← Trang giới thiệu</Link>
      </header>

      <section className="ovg-login-page-main">
        <div className="ovg-login-intro">
          <span className="ovg-eyebrow">KHÔNG GIAN LÀM VIỆC</span>
          <h1>Dữ liệu không gian của bạn, trong đúng phạm vi được cấp.</h1>
          <p>
            OpenVietGIS dùng nhà cung cấp định danh đã cấu hình để xác thực tài khoản.
            Quyền tổ chức, dự án và tài nguyên được kiểm tra bởi hệ thống OpenVietGIS.
          </p>
          <ul>
            <li>Phiên đăng nhập bảo mật</li>
            <li>Phân quyền theo tổ chức và tài nguyên</li>
            <li>Quay lại đúng màn hình bạn đang mở sau đăng nhập</li>
          </ul>
        </div>

        <div id="login-card" className="ovg-login-card" aria-labelledby="login-title">
          <span className="ovg-login-logo">OVG</span>
          <h2 id="login-title">Đăng nhập OpenVietGIS</h2>
          <p>Sử dụng tài khoản được cấp để tiếp tục.</p>

          {providers.isLoading ? (
            <div className="ovg-login-state" aria-live="polite">
              Đang tải phương thức đăng nhập…
            </div>
          ) : null}
          {providers.error ? (
            <div className="ovg-login-error" role="alert">
              Không thể tải phương thức đăng nhập. Hãy kiểm tra kết nối và thử lại.
            </div>
          ) : null}

          <div className="ovg-provider-list">
            {providers.data?.map((provider) => (
              <a
                className="ovg-provider-button"
                key={provider.id}
                href={loginUrl(provider, returnTo)}
              >
                <span className="ovg-provider-icon" aria-hidden="true">→</span>
                <span>Đăng nhập với {provider.display_name}</span>
              </a>
            ))}
          </div>

          <small className="ovg-login-note">
            Sau khi đăng nhập, bạn chỉ thấy những tổ chức và tài nguyên mà tài khoản hiện tại được cấp quyền.
          </small>
        </div>
      </section>
    </main>
  );
}
