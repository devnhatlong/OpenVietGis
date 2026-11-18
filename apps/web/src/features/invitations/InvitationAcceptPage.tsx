import { acceptInvitation, ApiError, loadCsrfToken } from "@openvietgis/client-sdk";
import { useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { apiClient } from "../../app/api";
import { FreshAccount } from "../auth/FreshAccount";

function parseHandoff(raw: string) {
  const data: unknown = JSON.parse(raw);
  if (!data || typeof data !== "object") throw new Error("Invalid invitation");
  if (!("organization_id" in data) || typeof data.organization_id !== "string" ||
      !("invitation_id" in data) || typeof data.invitation_id !== "string" ||
      !("secret" in data) || typeof data.secret !== "string" || data.secret.length < 32) {
    throw new Error("Invalid invitation");
  }
  return { organization_id: data.organization_id, invitation_id: data.invitation_id, secret: data.secret };
}

function AcceptForm({ userId }: { userId: string }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [handoff, setHandoff] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    setError("");
    setPending(true);
    try {
      const input = parseHandoff(handoff);
      await loadCsrfToken(apiClient);
      const result = await acceptInvitation(apiClient, input);
      setHandoff("");
      await queryClient.invalidateQueries({ queryKey: ["my-organizations", userId] });
      await navigate("/organizations/" + encodeURIComponent(result.membership.organization_id));
    } catch (error) {
      setError("Unable to accept invitation. Verify the details and sign in with the intended identity.");
      setHandoff("");
      if (error instanceof ApiError && error.status === 401) {
        await queryClient.invalidateQueries({ queryKey: ["me"] });
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <main style={{ maxWidth: 800, margin: "40px auto", fontFamily: "system-ui, sans-serif" }}>
      <Link to="/">← Organizations</Link>
      <h1>Accept invitation</h1>
      <p>Paste the private invitation details after signing in as the intended recipient. The secret is sent only in the protected request body.</p>
      <form onSubmit={(event) => void submit(event)}>
        <label>Invitation handoff
          <textarea rows={5} required autoComplete="off" spellCheck={false} value={handoff} onChange={(event) => setHandoff(event.target.value)} />
        </label>
        <button type="submit" disabled={pending}>Accept invitation</button>
      </form>
      {error ? <p role="alert">{error}</p> : null}
    </main>
  );
}

export function InvitationAcceptPage() {
  return <FreshAccount>{(account) => <AcceptForm key={account.id} userId={account.id} />}</FreshAccount>;
}
