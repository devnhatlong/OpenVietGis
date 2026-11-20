import {
  listIdentityProviders,
  type IdentityProviderSummary
} from "@openvietgis/client-sdk";
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "../../app/api";

function loginUrl(provider: IdentityProviderSummary): string {
  const returnTo = encodeURIComponent(window.location.pathname || "/");
  return (
    "/api/v1/auth/login/" +
    encodeURIComponent(provider.id) +
    "?return_to=" +
    returnTo
  );
}

export function LoginPanel() {
  const providers = useQuery({
    queryKey: ["identity-providers"],
    queryFn: () => listIdentityProviders(apiClient)
  });

  return (
    <section aria-labelledby="login-title">
      <h1 id="login-title">Đăng nhập OpenVietGIS</h1>
      <p>Xác thực an toàn thông qua nhà cung cấp định danh đã cấu hình.</p>
      {providers.isLoading ? <p>Đang tải nhà cung cấp đăng nhập…</p> : null}
      {providers.error ? <p role="alert">Không thể tải danh sách nhà cung cấp đăng nhập.</p> : null}
      <div>
        {providers.data?.map((provider) => (
          <a key={provider.id} href={loginUrl(provider)}>
            Đăng nhập với {provider.display_name}
          </a>
        ))}
      </div>
    </section>
  );
}
