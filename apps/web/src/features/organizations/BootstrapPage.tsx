import { ApiError, initializeInstallation, loadCsrfToken } from "@openvietgis/client-sdk";
import type { FormEvent } from "react";
import { useRef, useState } from "react";

import { apiClient } from "../../app/api";

export function BootstrapPage({ onInitialized }: { onInitialized: () => Promise<void> }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const authorityInput = useRef<HTMLInputElement>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const form = new FormData(event.currentTarget);
    const name = String(form.get("organization_name") ?? "").trim();
    const slug = String(form.get("organization_slug") ?? "").trim().toLowerCase();
    const authority = authorityInput.current?.value ?? "";
    if (authorityInput.current) authorityInput.current.value = "";
    setPending(true);
    setError("");
    try {
      await loadCsrfToken(apiClient);
      await initializeInstallation(apiClient, {
        organization_name: name,
        organization_slug: slug
      }, authority);
      await onInitialized();
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 409) {
        await onInitialized();
      } else {
        setError("Initialization failed. Check your session, authority and organization details.");
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <main>
      <h1>Initialize OpenVietGIS</h1>
      <p>Create the first organization and its Owner using the installation authority.</p>
      <form onSubmit={submit}>
        <label>
          Organization name
          <input name="organization_name" required maxLength={200} />
        </label>
        <label>
          Organization slug
          <input name="organization_slug" required maxLength={120}
            pattern="[a-z0-9]+(-[a-z0-9]+)*" />
        </label>
        <label>
          Installation authority
          <input ref={authorityInput} type="password" required autoComplete="off" />
        </label>
        <button type="submit" disabled={pending}>
          {pending ? "Initializing…" : "Initialize installation"}
        </button>
      </form>
      {error ? <p role="alert">{error}</p> : null}
    </main>
  );
}
