import type { ReactNode } from "react";

export function StatusMessage({
  kind = "info",
  children
}: {
  kind?: "info" | "success" | "warning" | "error";
  children: ReactNode;
}) {
  return (
    <div
      className={"ovg-status-message is-" + kind}
      role={kind === "error" ? "alert" : "status"}
    >
      {children}
    </div>
  );
}
