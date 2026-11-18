import {
  ApiError, createResourceGrant, getCurrentUser, getEffectivePermissions,
  listOrganizationMembers, listProjects, listResourceGrants, listWorkspaces,
  loadCsrfToken, revokeResourceGrant, updateOrganizationMembership,
  type MembershipUpdate
} from "@openvietgis/client-sdk";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { apiClient } from "../../app/api";
import { LoginPanel } from "../auth/LoginPanel";
import { InvitationIssuePanel } from "../invitations/InvitationIssuePanel";
import { initialScope, ResourceScopeFields, selectedGrant } from "./ResourceScopeFields";

function MemberAdministration({ organizationId, userId, permissions }: {
  organizationId: string;
  userId: string;
  permissions: string[];
}) {
  const queryClient = useQueryClient();
  const [membershipId, setMembershipId] = useState("");
  const [scope, setScope] = useState(initialScope);
  const canManageMembers = permissions.includes("organization.manage_members");
  const canManageGrants = permissions.includes("authorization.manage_grants");
  const canManageInvitations = permissions.includes("invitation.manage");

  const members = useQuery({
    queryKey: ["members", organizationId, userId],
    queryFn: () => listOrganizationMembers(apiClient, organizationId),
    enabled: canManageMembers || canManageGrants,
    staleTime: 0
  });
  const grants = useQuery({
    queryKey: ["grants", organizationId, userId],
    queryFn: () => listResourceGrants(apiClient, organizationId),
    enabled: canManageGrants,
    staleTime: 0
  });
  const workspaces = useQuery({
    queryKey: ["workspaces", organizationId, userId],
    queryFn: () => listWorkspaces(apiClient, organizationId),
    enabled: canManageGrants || canManageInvitations,
    staleTime: 0
  });
  const projects = useQuery({
    queryKey: ["projects", organizationId, userId],
    queryFn: () => listProjects(apiClient, organizationId),
    enabled: canManageGrants || canManageInvitations,
    staleTime: 0
  });

  async function refreshAccess() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["my-organizations"] }),
      queryClient.invalidateQueries({ queryKey: ["members", organizationId] }),
      queryClient.invalidateQueries({ queryKey: ["grants", organizationId] }),
      queryClient.invalidateQueries({ queryKey: ["permissions", organizationId] }),
      queryClient.invalidateQueries({ queryKey: ["workspaces", organizationId] }),
      queryClient.invalidateQueries({ queryKey: ["projects", organizationId] })
    ]);
  }

  const changeMember = useMutation({
    mutationFn: async ({ id, change }: { id: string; change: MembershipUpdate }) => {
      await loadCsrfToken(apiClient);
      await updateOrganizationMembership(apiClient, organizationId, id, change);
    },
    onSuccess: refreshAccess
  });
  const grantAccess = useMutation({
    mutationFn: async () => {
      const grant = selectedGrant(scope);
      if (!grant || !membershipId) throw new Error("Missing grant target");
      await loadCsrfToken(apiClient);
      await createResourceGrant(apiClient, organizationId, {
        ...grant, subject_kind: "membership", subject_id: membershipId
      });
    },
    onSuccess: async () => {
      setMembershipId("");
      await refreshAccess();
    }
  });
  const revokeAccess = useMutation({
    mutationFn: async (id: string) => {
      await loadCsrfToken(apiClient);
      await revokeResourceGrant(apiClient, organizationId, id);
    },
    onSuccess: refreshAccess
  });

  function submitGrant(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!grantAccess.isPending && membershipId && selectedGrant(scope)) grantAccess.mutate();
  }

  const availableWorkspaces = workspaces.error || workspaces.isFetching ? [] : workspaces.data ?? [];
  const availableProjects = projects.error || projects.isFetching ? [] : projects.data ?? [];
  const availableMembers = members.error || members.isFetching ? [] : members.data ?? [];

  return (
    <>
      {canManageMembers ? (
        <section>
          <h2>Members</h2>
          {members.isFetching ? <p>Loading members…</p> : null}
          {members.error ? <p role="alert">Unable to load members.</p> : null}
          <ul data-testid="member-list">
            {availableMembers.map((member) => (
              <li key={member.id} data-testid={"member-" + member.id}>
                {member.user_id}{member.user_id === userId ? " (you)" : ""} — {member.role} — {member.status}{" "}
                {member.status === "active" ? (
                  <button type="button" disabled={changeMember.isPending} onClick={() => changeMember.mutate({ id: member.id, change: { status: "suspended" } })}>Suspend</button>
                ) : member.status === "suspended" ? (
                  <button type="button" disabled={changeMember.isPending} onClick={() => changeMember.mutate({ id: member.id, change: { status: "active" } })}>Restore</button>
                ) : null}
                {member.status !== "revoked" ? (
                  <button type="button" disabled={changeMember.isPending} onClick={() => {
                    if (window.confirm("Revoke this membership?")) changeMember.mutate({ id: member.id, change: { status: "revoked" } });
                  }}>Revoke</button>
                ) : null}
              </li>
            ))}
          </ul>
          {changeMember.error ? <p role="alert">Unable to change membership. The server enforces Owner and lifecycle rules.</p> : null}
        </section>
      ) : null}

      {canManageGrants ? (
        <section>
          <h2>Resource grants</h2>
          <form onSubmit={submitGrant}>
            <label>Membership
              <select required value={membershipId} onChange={(event) => setMembershipId(event.target.value)}>
                <option value="">Select member</option>
                {availableMembers.filter((member) => member.status === "active").map((member) => (
                  <option key={member.id} value={member.id}>{member.user_id} — {member.role}</option>
                ))}
              </select>
            </label>
            <ResourceScopeFields label="Grant resource access" value={scope} onChange={setScope} workspaces={availableWorkspaces} projects={availableProjects} />
            <button type="submit" disabled={grantAccess.isPending}>Create grant</button>
          </form>
          {grants.isFetching ? <p>Loading grants…</p> : null}
          {grants.error || workspaces.error || projects.error ? <p role="alert">Unable to load grant resources.</p> : null}
          <ul data-testid="resource-grant-list">
            {!grants.isFetching && !grants.error ? grants.data?.map((grant) => (
              <li key={grant.id}>
                {grant.subject_id} — {grant.role} — {grant.scope_kind} {grant.workspace_id ?? grant.project_id ?? ""} — {grant.revoked_at ? "revoked" : "active"}{" "}
                {!grant.revoked_at ? (
                  <button type="button" disabled={revokeAccess.isPending} onClick={() => revokeAccess.mutate(grant.id)}>Revoke grant</button>
                ) : null}
              </li>
            )) : null}
          </ul>
          {grantAccess.error || revokeAccess.error ? <p role="alert">Unable to update grant.</p> : null}
        </section>
      ) : null}

      {canManageInvitations ? (
        <InvitationIssuePanel organizationId={organizationId} workspaces={availableWorkspaces} projects={availableProjects} />
      ) : null}
      {!canManageMembers && !canManageGrants && !canManageInvitations ? (
        <p>You do not have permission to administer this organization.</p>
      ) : null}
    </>
  );
}

function OrganizationMembership({ organizationId, userId }: { organizationId: string; userId: string }) {
  const effective = useQuery({
    queryKey: ["permissions", organizationId, userId],
    queryFn: () => getEffectivePermissions(apiClient, organizationId),
    staleTime: 0,
    refetchOnMount: "always"
  });

  return (
    <main style={{ maxWidth: 960, margin: "40px auto", fontFamily: "system-ui, sans-serif" }}>
      <Link to={"/organizations/" + encodeURIComponent(organizationId)}>← Organization</Link>
      <h1>Membership and access</h1>
      {effective.isFetching ? <p>Checking organization permissions…</p> : effective.error || !effective.data ? (
        <p role="alert">Unable to load organization access.</p>
      ) : (
        <MemberAdministration organizationId={organizationId} userId={userId} permissions={effective.data.permissions} />
      )}
    </main>
  );
}

export function MembershipPage() {
  const { organizationId } = useParams();
  const user = useQuery({ queryKey: ["me"], queryFn: () => getCurrentUser(apiClient), staleTime: 0, refetchOnMount: "always" });
  if (!organizationId) return <p role="alert">Organization context is missing.</p>;
  if (user.isFetching) return <p>Checking your account…</p>;
  if (user.error instanceof ApiError && user.error.status === 401) return <LoginPanel />;
  if (user.error || !user.data) return <p role="alert">Unable to load your account.</p>;
  return <OrganizationMembership key={organizationId + ":" + user.data.id} organizationId={organizationId} userId={user.data.id} />;
}
