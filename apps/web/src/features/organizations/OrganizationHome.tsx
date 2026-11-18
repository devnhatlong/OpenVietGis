import {
  ApiError,
  createOrganization,
  listMyOrganizations,
  loadCsrfToken,
  type CurrentUser
} from "@openvietgis/client-sdk";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { apiClient } from "../../app/api";
import { currentProtectedData, protectedQueryOptions } from "../../app/protected-query";
import { FreshAccount } from "../auth/FreshAccount";

function slugify(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function OrganizationList({ organizationId, account }: { organizationId: string | undefined; account: CurrentUser }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");

  const organizations = useQuery({
    queryKey: ["my-organizations", account.id],
    queryFn: () => listMyOrganizations(apiClient),
    ...protectedQueryOptions
  });

  async function refreshOrganizations() {
    await queryClient.invalidateQueries({ queryKey: ["my-organizations", account.id] });
  }

  const create = useMutation({
    mutationFn: async (input: { name: string; slug: string }) => {
      await loadCsrfToken(apiClient);
      return createOrganization(apiClient, input);
    },
    onSuccess: async () => {
      setName("");
      setSlug("");
      await refreshOrganizations();
    },
    onError: refreshOrganizations
  });

  const visibleOrganizations = currentProtectedData(organizations);
  if (!visibleOrganizations) {
    const checking = !organizations.error &&
      (organizations.isPending || organizations.fetchStatus !== "idle");
    return (
      <main>
        <h1>Organizations</h1>
        {checking ? <p>Checking organization access…</p> : <p role="alert">Unable to load organization access.</p>}
      </main>
    );
  }

  const activeOrganization = visibleOrganizations.find((item) => item.id === organizationId);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedSlug = slugify(slug || name);
    if (!normalizedSlug) return;
    create.mutate({ name: name.trim(), slug: normalizedSlug });
  }

  return (
    <main style={{ maxWidth: 880, margin: "40px auto", fontFamily: "system-ui, sans-serif" }}>
      <header>
        <p style={{ textTransform: "uppercase", letterSpacing: "0.12em" }}>OpenVietGIS</p>
        <h1>{activeOrganization ? activeOrganization.name : "Organizations"}</h1>
        <p>
          Signed in as <strong>{account.display_name}</strong>.{" "}
          <Link to="/identity">Identity & session</Link>{" "}
          <Link to="/invitations/accept">Accept invitation</Link>
        </p>
      </header>

      <section aria-labelledby="organization-switcher-title">
        <h2 id="organization-switcher-title">Your organizations</h2>
        <ul data-testid="organization-list">
          {visibleOrganizations.map((organization) => (
            <li key={organization.id}>
              <Link
                to={"/organizations/" + organization.id}
                aria-current={organization.id === organizationId ? "page" : undefined}
              >
                {organization.name}
              </Link>{" "}
              — {organization.role}
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="create-organization-title">
        <h2 id="create-organization-title">Create organization</h2>
        <form onSubmit={submit}>
          <label>
            Name
            <input
              aria-label="Organization name"
              value={name}
              onChange={(event) => {
                setName(event.target.value);
                if (!slug) setSlug(slugify(event.target.value));
              }}
              required
            />
          </label>
          <label>
            Slug
            <input
              aria-label="Organization slug"
              value={slug}
              onChange={(event) => setSlug(event.target.value)}
              required
            />
          </label>
          <button type="submit" disabled={create.isPending}>
            {create.isPending ? "Creating…" : "Create organization"}
          </button>
        </form>
        {create.error instanceof ApiError && create.error.status === 409 ? (
          <p role="alert">
            The installation must be initialized before creating another organization.
          </p>
        ) : create.error ? (
          <p role="alert">Organization creation failed.</p>
        ) : null}
      </section>

      {activeOrganization ? (
        <section aria-labelledby="active-organization-title">
          <h2 id="active-organization-title">Active organization context</h2>
          <p>
            <Link to={"/organizations/" + activeOrganization.id + "/workspaces"}>
              Workspaces
            </Link>{" "}
            <Link to={"/organizations/" + activeOrganization.id + "/projects"}>
              Projects
            </Link>{" "}
            <Link to={"/organizations/" + activeOrganization.id + "/membership"}>
              Membership and access
            </Link>
          </p>
          <dl data-testid="active-organization">
            <dt>ID</dt>
            <dd>{activeOrganization.id}</dd>
            <dt>Role</dt>
            <dd>{activeOrganization.role}</dd>
          </dl>
        </section>
      ) : null}
    </main>
  );
}

export function OrganizationHome() {
  const { organizationId } = useParams();
  return (
    <FreshAccount key={organizationId ?? "home"}>
      {(account) => (
        <OrganizationList
          key={account.id}
          organizationId={organizationId}
          account={account}
        />
      )}
    </FreshAccount>
  );
}
