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
        setError("Khởi tạo thất bại. Vui lòng kiểm tra phiên đăng nhập, mã bí mật và thông tin tổ chức.");
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <main>
      <h1>Khởi tạo hệ thống OpenVietGIS</h1>
      <p>Tạo tổ chức đầu tiên và tài khoản Chủ sở hữu bằng mã bí mật cài đặt.</p>
      <form onSubmit={submit}>
        <label>
          Tên tổ chức
          <input name="organization_name" required maxLength={200} />
        </label>
        <label>
          Mã định danh (slug)
          <input name="organization_slug" required maxLength={120}
            pattern="[a-z0-9]+(-[a-z0-9]+)*" />
        </label>
        <label>
          Mã bí mật khởi tạo (Bootstrap Secret)
          <input ref={authorityInput} type="password" required autoComplete="off" />
        </label>
        <button type="submit" disabled={pending}>
          {pending ? "Đang khởi tạo…" : "Khởi tạo hệ thống"}
        </button>
      </form>
      {error ? <p role="alert">{error}</p> : null}
    </main>
  );
}
