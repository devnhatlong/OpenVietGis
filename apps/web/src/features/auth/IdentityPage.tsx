import {
  ApiError,
  getCurrentUser,
  listIdentityLinks,
  listIdentityProviders,
  loadCsrfToken,
  logout,
  unlinkIdentity
} from "@openvietgis/client-sdk";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";

import { apiClient } from "../../app/api";
import { LoginPanel } from "./LoginPanel";

export function IdentityPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const user = useQuery({ queryKey: ["me"], queryFn: () => getCurrentUser(apiClient) });
  const links = useQuery({
    queryKey: ["identity-links"],
    queryFn: () => listIdentityLinks(apiClient),
    enabled: user.isSuccess
  });
  const providers = useQuery({
    queryKey: ["identity-providers"],
    queryFn: () => listIdentityProviders(apiClient),
    enabled: user.isSuccess
  });

  const unlink = useMutation({
    mutationFn: async (identityLinkId: string) => {
      await loadCsrfToken(apiClient);
      await unlinkIdentity(apiClient, identityLinkId);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["identity-links"] });
    }
  });

  const signOut = useMutation({
    mutationFn: async () => {
      await loadCsrfToken(apiClient);
      await logout(apiClient);
    },
    onSuccess: async () => {
      queryClient.clear();
      await navigate("/");
    }
  });

  if (user.error instanceof ApiError && user.error.status === 401) {
    return <LoginPanel />;
  }
  if (!user.data) return <p>Loading identity…</p>;

  return (
    <main style={{ maxWidth: 800, margin: "40px auto", fontFamily: "system-ui, sans-serif" }}>
      <p>
        <Link to="/">← Organizations</Link>
      </p>
      <h1>Identity & session</h1>
      <p>
        {user.data.display_name}
        {user.data.email_snapshot ? " — " + user.data.email_snapshot : ""}
      </p>

      <h2>Linked identities</h2>
      <ul>
        {links.data?.map((link) => (
          <li key={link.id}>
            {link.issuer} / {link.subject}
            {links.data && links.data.length > 1 ? (
              <button type="button" onClick={() => unlink.mutate(link.id)}>
                Unlink
              </button>
            ) : null}
          </li>
        ))}
      </ul>

      <h2>Link another identity</h2>
      {providers.data?.map((provider) => (
        <p key={provider.id}>
          <a
            href={
              "/api/v1/auth/login/" +
              encodeURIComponent(provider.id) +
              "?mode=link&return_to=/identity"
            }
          >
            Link {provider.display_name}
          </a>
        </p>
      ))}

      <button type="button" onClick={() => signOut.mutate()} disabled={signOut.isPending}>
        Sign out
      </button>
      {unlink.error ? <p role="alert">Unable to unlink identity.</p> : null}
      {signOut.error ? <p role="alert">Unable to sign out.</p> : null}
    </main>
  );
}
