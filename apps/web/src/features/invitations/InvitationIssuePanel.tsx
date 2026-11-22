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
        target: recipient,
        organization_role: role,
        resource_grant: resourceGrant ?? null,
        expires_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString()
      });
      setIssued(result);
      setRevokeId(result.id);
      setTarget("");
      setSubject("");
    } catch (err) {
      setError("Không thể gửi lời mời.");
      await onAccessError(err);
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
      setMessage("Đã thu hồi lời mời.");
    } catch (err) {
      setError("Không thể thu hồi lời mời.");
      await onAccessError(err);
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="rounded-2xl border border-line bg-surface p-5 shadow-xs space-y-5">
      <h2 className="text-base font-bold text-ink">Lời mời thành viên</h2>

      <form onSubmit={(event) => void issue(event)} className="space-y-4 rounded-xl border border-line bg-surface-muted p-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 items-end">
          <label className="flex flex-col gap-1.5 text-xs font-semibold text-ink-secondary">
            <span>Loại người nhận</span>
            <select
              className="w-full"
              value={kind}
              onChange={(event) => {
                setKind(event.target.value as InvitationCreate["target"]["kind"]);
                setTarget("");
                setSubject("");
              }}
            >
              <option value="email">Email đã xác minh</option>
              <option value="user">Mã người dùng</option>
              <option value="external_identity">Danh tính bên ngoài</option>
            </select>
          </label>
          <label className="flex flex-col gap-1.5 text-xs font-semibold text-ink-secondary">
            <span>{kind === "email" ? "Email người nhận" : kind === "user" ? "Mã người dùng nhận lời mời" : "Nhà phát hành danh tính"}</span>
            <input
              required
              className="w-full"
              type={kind === "email" ? "email" : kind === "external_identity" ? "url" : "text"}
              placeholder={kind === "email" ? "ten@congty.vn" : ""}
              value={target}
              onChange={(event) => setTarget(event.target.value)}
            />
          </label>
          {kind === "external_identity" ? (
            <label className="flex flex-col gap-1.5 text-xs font-semibold text-ink-secondary">
              <span>Định danh người dùng</span>
              <input required className="w-full" value={subject} onChange={(event) => setSubject(event.target.value)} />
            </label>
          ) : null}
          <label className="flex flex-col gap-1.5 text-xs font-semibold text-ink-secondary">
            <span>Vai trò trong tổ chức</span>
            <select
              className="w-full"
              value={role}
              onChange={(event) => setRole(event.target.value as InvitationCreate["organization_role"])}
            >
              <option value="guest">Khách</option>
              <option value="member">Thành viên</option>
              <option value="admin">Quản trị viên</option>
            </select>
          </label>
          <div>
            <button
              type="submit"
              disabled={pending || (withGrant && !resourceGrant)}
              className="inline-flex w-full items-center justify-center rounded-lg bg-brand px-4 py-2 text-sm font-bold text-brand-fg hover:bg-brand-strong disabled:opacity-50 cursor-pointer"
            >
              Gửi lời mời
            </button>
          </div>
        </div>

        <label className="inline-flex items-center gap-2 text-xs font-semibold text-ink-secondary cursor-pointer">
          <input type="checkbox" checked={withGrant} onChange={(event) => setWithGrant(event.target.checked)} />
          <span>Kèm quyền truy cập tài nguyên</span>
        </label>

        {withGrant ? (
          <ResourceScopeFields
            label="Quyền tài nguyên trong lời mời"
            value={scope}
            onChange={setScope}
            workspaces={workspaces}
            projects={projects}
          />
        ) : null}
      </form>

      {issued ? (
        <section aria-label="Lời mời đã tạo" className="rounded-xl border border-brand/40 bg-brand-soft p-4 space-y-3">
          <p className="text-xs font-medium text-ink">
            Chia sẻ thông tin lời mời riêng cho đúng người nhận. Mã bí mật chỉ hiển thị một lần.
          </p>
          <label className="flex flex-col gap-1.5 text-xs font-semibold text-ink-secondary">
            <span>Thông tin lời mời</span>
            <textarea
              readOnly
              rows={4}
              className="w-full font-mono text-xs"
              value={JSON.stringify({
                organization_id: issued.organization_id,
                invitation_id: issued.id,
                secret: issued.secret
              })}
            />
          </label>
          <button
            type="button"
            className="rounded-lg border border-line-strong bg-surface px-3 py-1.5 text-xs font-semibold text-ink-secondary cursor-pointer"
            onClick={() => setIssued(null)}
          >
            Ẩn mã bí mật dùng một lần
          </button>
        </section>
      ) : null}

      <form onSubmit={(event) => void revoke(event)} className="flex flex-wrap items-end gap-3 border-t border-line pt-4">
        <label className="flex flex-col gap-1.5 text-xs font-semibold text-ink-secondary min-w-[260px] flex-1 max-w-md">
          <span>Mã lời mời cần thu hồi</span>
          <input required className="w-full" placeholder="Nhập UUID lời mời…" value={revokeId} onChange={(event) => setRevokeId(event.target.value)} />
        </label>
        <button
          type="submit"
          disabled={pending}
          className="rounded-lg border border-danger/50 bg-surface px-4 py-2 text-xs font-bold text-danger hover:bg-danger-soft disabled:opacity-50 cursor-pointer"
        >
          Thu hồi lời mời
        </button>
      </form>

      {message ? <p role="status" className="rounded-lg bg-brand-soft px-3 py-2 text-xs font-semibold text-brand">{message}</p> : null}
      {error ? <p role="alert" className="rounded-lg bg-danger-soft px-3 py-2 text-xs font-semibold text-danger">{error}</p> : null}
    </section>
  );
}
