import {
  ApiError,
  loadCsrfToken,
  logout
} from "@openvietgis/client-sdk";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";

import { apiClient } from "../../app/api";
import { useOptionalSession } from "../../app/session/SessionBoundary";
import { buildAccountMenuState } from "./account-menu-state";
import { lockOfflineActor } from "../offline/offline-store";
import "./account-menu.css";

export function AccountMenu() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const session = useOptionalSession();

  const signOut = useMutation({
    mutationFn: async () => {
      lockOfflineActor();
      await loadCsrfToken(apiClient);
      await logout(apiClient);
    },
    onSuccess: async () => {
      queryClient.clear();
      await navigate("/");
    },
    onError: async (error) => {
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      if (error instanceof ApiError && error.status === 401) {
        queryClient.clear();
        await navigate("/");
      }
    }
  });

  if (!session) return null;
  const { account } = session;
  const state = buildAccountMenuState(
    account,
    session.checking,
    session.networkWarning
  );

  return (
    <details className="ovg-account-menu">
      <summary role="button" aria-label="Mở menu tài khoản">
        <span className="ovg-account-avatar">{state.initials}</span>
        <span className="ovg-account-name">{state.displayName}</span>
        <span className="ovg-account-caret" aria-hidden="true">⌄</span>
      </summary>
      <div className="ovg-account-dropdown">
        <div className="ovg-account-profile">
          <strong>{state.displayName}</strong>
          {state.email ? <small>{state.email}</small> : null}
          {state.checking ? <small>Đang xác nhận phiên…</small> : null}
          {state.networkWarning ? <small>Phiên đang dùng; kiểm tra mạng chưa hoàn tất.</small> : null}
        </div>
        <nav aria-label="Tài khoản">
          <Link to="/app">Trang làm việc</Link>
          <Link to="/app/account">Tài khoản & phiên đăng nhập</Link>
          <Link to="/app/invitations/accept">Lời mời</Link>
        </nav>
        <button
          type="button"
          className="ovg-signout-button"
          disabled={signOut.isPending}
          onClick={() => signOut.mutate()}
        >
          {signOut.isPending ? "Đang đăng xuất…" : "Đăng xuất"}
        </button>
        {signOut.error ? <p role="alert">Không thể đăng xuất. Hãy thử lại.</p> : null}
      </div>
    </details>
  );
}
