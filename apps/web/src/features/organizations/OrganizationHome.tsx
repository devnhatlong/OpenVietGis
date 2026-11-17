import {
  ApiError,
  createOrganization,
  getCurrentUser,
  listMyOrganizations,
  loadCsrfToken
} from "@openvietgis/client-sdk";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { apiClient } from "../../app/api";
import { LoginPanel } from "../auth/LoginPanel";

function slugify(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

export function OrganizationHome() {
  const { organizationId } = useParams();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");

  const user = useQuery({
    queryKey: ["me"],
    queryFn: () => getCurrentUser(apiClient)
  });
  const organizations = useQuery({
    queryKey: ["my-organizations"],
    queryFn: () => listMyOrganizations(apiClient),
    enabled: user.isSuccess
  });

  const create = useMutation({
    mutationFn: async (input: { name: string; slug: string }) => {
      await loadCsrfToken(apiClient);
      return createOrganization(apiClient, input);
    },
    onSuccess: async () => {
      setName("");
      setSlug("");
      await queryClient.invalidateQueries({ queryKey: ["my-organizations"] });
    }
  });

  if (user.error instanceof ApiError && user.error.status === 401) {
    return <LoginPanel />;
  }

  if (user.isLoading) {
    return <p>Loading your OpenVietGIS account…</p>;
  }

  if (user.error || !user.data) {
    return <p role="alert">Unable to load your account.</p>;
  }

  const activeOrganization = organizations.data?.find(
    (item) => item.id === organizationId
  );

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
          Signed in as <strong>{user.data.display_name}</strong>.{" "}
          <Link to="/identity">Identity & session</Link>
        </p>
      </header>

      <section aria-labelledby="organization-switcher-title">
        <h2 id="organization-switcher-title">Your organizations</h2>
        {organizations.isLoading ? <p>Loading organizations…</p> : null}
        {organizations.error ? <p role="alert">Unable to load organizations.</p> : null}
        <ul data-testid="organization-list">
          {organizations.data?.map((organization) => (
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
