import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { buildShellCommands } from "./command-registry";

export function CommandPalette() {
  const { organizationId, projectId } = useParams();
  const navigate = useNavigate();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");

  const commands = useMemo(
    () => buildShellCommands(organizationId, projectId),
    [organizationId, projectId]
  );

  const filtered = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("vi");
    if (!normalized) return commands;
    return commands.filter((command) =>
      (command.label + " " + command.keywords)
        .toLocaleLowerCase("vi")
        .includes(normalized)
    );
  }, [commands, query]);

  function open() {
    setQuery("");
    dialogRef.current?.showModal();
    requestAnimationFrame(() => inputRef.current?.focus());
  }

  function close() {
    dialogRef.current?.close();
  }

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        if (dialogRef.current?.open) close();
        else open();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <>
      <button
        type="button"
        className="ovg-command-trigger"
        onClick={open}
        aria-haspopup="dialog"
      >
        <span>Lệnh nhanh</span>
        <kbd>Ctrl K</kbd>
      </button>

      <dialog
        ref={dialogRef}
        className="ovg-command-dialog"
        aria-labelledby="ovg-command-title"
        onClose={() => setQuery("")}
      >
        <div className="ovg-command-dialog-head">
          <div>
            <strong id="ovg-command-title">Lệnh nhanh</strong>
            <small>Đi tới khu vực đang khả dụng trong ngữ cảnh hiện tại.</small>
          </div>
          <button type="button" onClick={close} aria-label="Đóng bảng lệnh">×</button>
        </div>
        <label className="ovg-command-search">
          <span className="sr-only">Tìm lệnh</span>
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Tìm dự án, bản đồ, dữ liệu…"
          />
        </label>
        <div className="ovg-command-results" role="list">
          {filtered.length ? filtered.map((command) => (
            <button
              type="button"
              role="listitem"
              key={command.id}
              onClick={() => {
                close();
                void navigate(command.destination);
              }}
            >
              {command.label}
            </button>
          )) : <p>Không có lệnh phù hợp.</p>}
        </div>
      </dialog>
    </>
  );
}
