import {
  acceptInvitation,
  ApiError,
  loadCsrfToken
} from "@openvietgis/client-sdk";
import { useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { apiClient } from "../../app/api";
import { FreshAccount } from "../auth/FreshAccount";
import "./invitation.css";

function parseHandoff(raw: string) {
  const data: unknown = JSON.parse(raw);
  if (!data || typeof data !== "object") throw new Error("Invalid invitation");
  if (
    !("organization_id" in data) ||
    typeof data.organization_id !== "string" ||
    !("invitation_id" in data) ||
    typeof data.invitation_id !== "string" ||
    !("secret" in data) ||
    typeof data.secret !== "string" ||
    data.secret.length < 32
  ) {
    throw new Error("Invalid invitation");
  }

  return {
    organization_id: data.organization_id,
    invitation_id: data.invitation_id,
    secret: data.secret
  };
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
      await queryClient.invalidateQueries({
        queryKey: ["my-organizations", userId]
      });
      await queryClient.invalidateQueries({
        queryKey: ["app-dashboard", userId]
      });
      await navigate(
        "/app/organizations/" +
          encodeURIComponent(result.membership.organization_id)
      );
    } catch (caught) {
      setError(
        "Không thể chấp nhận lời mời. Hãy kiểm tra thông tin và đăng nhập đúng tài khoản người nhận."
      );
      setHandoff("");
      if (caught instanceof ApiError && caught.status === 401) {
        await queryClient.invalidateQueries({ queryKey: ["me"] });
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="invitation-page">
      <header className="invitation-page-head">
        <span className="app-dashboard-kicker">LỜI MỜI</span>
        <h1>Chấp nhận lời mời</h1>
        <p>
          Dán thông tin lời mời riêng tư được gửi cho bạn. Mã bí mật chỉ dùng
          trong yêu cầu được bảo vệ và không được lưu lại sau khi xử lý.
        </p>
      </header>

      <section className="invitation-card">
        <form onSubmit={(event) => void submit(event)}>
          <label>
            Thông tin lời mời
            <textarea
              aria-label="Thông tin lời mời"
              rows={5}
              required
              autoComplete="off"
              spellCheck={false}
              value={handoff}
              onChange={(event) => setHandoff(event.target.value)}
              placeholder='{"organization_id":"…","invitation_id":"…","secret":"…"}'
            />
          </label>

          <div className="invitation-help">
            Chỉ chấp nhận lời mời từ nguồn bạn tin cậy. OpenVietGIS sẽ kiểm tra
            tài khoản người nhận và quyền phía máy chủ trước khi thêm thành viên.
          </div>

          <button type="submit" disabled={pending}>
            {pending ? "Đang chấp nhận…" : "Chấp nhận lời mời"}
          </button>
        </form>

        {error ? (
          <p className="invitation-alert" role="alert">
            {error}
          </p>
        ) : null}
      </section>
    </main>
  );
}

export function InvitationAcceptPage() {
  return (
    <FreshAccount>
      {(account) => <AcceptForm key={account.id} userId={account.id} />}
    </FreshAccount>
  );
}
