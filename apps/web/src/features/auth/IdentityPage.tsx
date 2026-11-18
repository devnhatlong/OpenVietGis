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
import { Link, useNavigate } from "react-router-dom";

import { apiClient } from "../../app/api";
import { currentProtectedData, identityLinksKey, protectedQueryOptions } from "../../app/protected-query";
import { FreshAccount } from "./FreshAccount";

function IdentityDetails({ account }: { account: CurrentUser }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
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
      await queryClient.invalidateQueries({ queryKey: linksKey });
    },
    onError: async (error) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: linksKey }),
        ...(error instanceof ApiError && (error.status === 401 || error.status === 403)
          ? [queryClient.invalidateQueries({ queryKey: ["me"] })] : [])
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
      await navigate("/");
    },
    onError: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["me"] }),
        queryClient.invalidateQueries({ queryKey: linksKey })
      ]);
    }
  });

  return (
    <main style={{ maxWidth: 800, margin: "40px auto", fontFamily: "system-ui, sans-serif" }}>
      <p>
        <Link to="/">← Organizations</Link>
      </p>
      <h1>Identity & session</h1>
      <p>
        {account.display_name}
        {account.email_snapshot ? " — " + account.email_snapshot : ""}
      </p>

      <h2>Linked identities</h2>
      {links.fetchStatus !== "idle" || links.isPending ? <p>Checking linked identities…</p> : !currentLinks ? <p role="alert">Unable to load linked identities.</p> : null}
      <ul>
        {currentLinks?.map((link) => (
          <li key={link.id}>
            {link.issuer} / {link.subject}
            {currentLinks.length > 1 ? (
              <button type="button" disabled={unlink.isPending || signOut.isPending} onClick={() => unlink.mutate(link.id)}>
                Unlink
              </button>
            ) : null}
          </li>
        ))}
      </ul>

      <h2>Link another identity</h2>
      {providers.fetchStatus !== "idle" || providers.isPending ? <p>Checking identity providers…</p> : !currentProviders ? <p role="alert">Unable to load identity providers.</p> : null}
      {currentLinks && !signOut.isPending && !unlink.isPending && currentProviders?.map((provider) => (
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

      <button type="button" onClick={() => signOut.mutate()} disabled={signOut.isPending || unlink.isPending}>
        Sign out
      </button>
      {unlink.error ? <p role="alert">Unable to unlink identity.</p> : null}
      {signOut.error ? <p role="alert">Unable to sign out.</p> : null}
    </main>
  );
}

export function IdentityPage() {
  return <FreshAccount>{(account) => <IdentityDetails key={account.id} account={account} />}</FreshAccount>;
}
