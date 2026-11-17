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
      <h1 id="login-title">Sign in to OpenVietGIS</h1>
      <p>Authentication is provided by your configured identity provider.</p>
      {providers.isLoading ? <p>Loading identity providers…</p> : null}
      {providers.error ? <p role="alert">Unable to load identity providers.</p> : null}
      <div>
        {providers.data?.map((provider) => (
          <a key={provider.id} href={loginUrl(provider)}>
            Continue with {provider.display_name}
          </a>
        ))}
      </div>
    </section>
  );
}
