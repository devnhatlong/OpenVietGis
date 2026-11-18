import {
  createInvitation, loadCsrfToken, revokeInvitation,
  type InvitationCreate, type InvitationIssued, type Project, type Workspace
} from "@openvietgis/client-sdk";
import { useState } from "react";
import type { FormEvent } from "react";

import { apiClient } from "../../app/api";
import { initialScope, ResourceScopeFields, selectedGrant } from "../membership/ResourceScopeFields";

export function InvitationIssuePanel({ organizationId, workspaces, projects, onAccessError }: {
  organizationId: string;
  workspaces: Workspace[];
  projects: Project[];
  onAccessError: (error: unknown) => Promise<void>;
}) {
  const [kind, setKind] = useState<InvitationCreate["target"]["kind"]>("email");
  const [target, setTarget] = useState("");
  const [subject, setSubject] = useState("");
  const [role, setRole] = useState<InvitationCreate["organization_role"]>("member");
  const [withGrant, setWithGrant] = useState(false);
  const [scope, setScope] = useState(initialScope);
  const [issued, setIssued] = useState<InvitationIssued | null>(null);
  const [revokeId, setRevokeId] = useState("");
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const resourceGrant = withGrant ? selectedGrant(scope, workspaces, projects) : null;

  async function issue(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    if (withGrant && !resourceGrant) return;
    const recipient: InvitationCreate["target"] = kind === "email"
      ? { kind, email: target.trim() }
      : kind === "user"
        ? { kind, user_id: target.trim() }
        : { kind, issuer: target.trim(), subject: subject.trim() };
    setPending(true);
    setError("");
    setMessage("");
    setIssued(null);
    try {
      await loadCsrfToken(apiClient);
      const result = await createInvitation(apiClient, organizationId, {
        target: recipient, organization_role: role,
        resource_grant: resourceGrant ?? null,
        expires_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString()
      });
      setIssued(result);
      setRevokeId(result.id);
      setTarget("");
      setSubject("");
    } catch (error) {
      // Never display raw response bodies; the response may contain a one-time secret.
      setError("Unable to issue invitation.");
      await onAccessError(error);
    } finally {
      setPending(false);
    }
  }

  async function revoke(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending || !revokeId.trim()) return;
    setPending(true);
    setError("");
    setMessage("");
    setIssued(null);
    try {
      await loadCsrfToken(apiClient);
      await revokeInvitation(apiClient, organizationId, revokeId.trim());
      setRevokeId("");
      setMessage("Invitation revoked.");
    } catch (error) {
      setError("Unable to revoke invitation.");
      await onAccessError(error);
    } finally {
      setPending(false);
    }
  }

  return (
    <section>
      <h2>Invitations</h2>
      <form onSubmit={(event) => void issue(event)}>
        <label>Recipient type
          <select value={kind} onChange={(event) => {
            setKind(event.target.value as InvitationCreate["target"]["kind"]);
            setTarget("");
            setSubject("");
          }}>
            <option value="email">Verified email</option>
            <option value="user">User ID</option>
            <option value="external_identity">External identity</option>
          </select>
        </label>
        <label>{kind === "email" ? "Recipient email" : kind === "user" ? "Recipient user ID" : "Identity issuer"}
          <input required type={kind === "email" ? "email" : kind === "external_identity" ? "url" : "text"}
            value={target} onChange={(event) => setTarget(event.target.value)} />
        </label>
        {kind === "external_identity" ? (
          <label>Identity subject<input required value={subject} onChange={(event) => setSubject(event.target.value)} /></label>
        ) : null}
        <label>Organization role
          <select value={role} onChange={(event) => setRole(event.target.value as InvitationCreate["organization_role"])}>
            <option value="guest">Guest</option>
            <option value="member">Member</option>
            <option value="admin">Admin</option>
          </select>
        </label>
        <label><input type="checkbox" checked={withGrant} onChange={(event) => setWithGrant(event.target.checked)} /> Include resource grant</label>
        {withGrant ? <ResourceScopeFields label="Invitation resource access" value={scope} onChange={setScope} workspaces={workspaces} projects={projects} /> : null}
        <p>Expires in 24 hours. The secret is shown once and will not be saved by this page.</p>
        <button type="submit" disabled={pending || (withGrant && !resourceGrant)}>Issue invitation</button>
      </form>
      {issued ? (
        <section aria-label="Issued invitation">
          <p>Share the invitation details privately with the intended recipient. They must sign in and open the invitation acceptance page.</p>
          <label>Invitation handoff
            <textarea readOnly rows={5} value={JSON.stringify({
              organization_id: issued.organization_id, invitation_id: issued.id, secret: issued.secret
            })} />
          </label>
          <button type="button" onClick={() => setIssued(null)}>Hide one-time secret</button>
        </section>
      ) : null}
      <form onSubmit={(event) => void revoke(event)}>
        <label>Invitation ID to revoke<input required value={revokeId} onChange={(event) => setRevokeId(event.target.value)} /></label>
        <button type="submit" disabled={pending}>Revoke invitation</button>
      </form>
      {message ? <p role="status">{message}</p> : null}
      {error ? <p role="alert">{error}</p> : null}
    </section>
  );
}
