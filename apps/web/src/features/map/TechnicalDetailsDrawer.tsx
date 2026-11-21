import {
  useEffect,
  useRef,
  type RefObject
} from "react";

import type { TechnicalDetailsView } from "./technical-details";

export function TechnicalDetailsDrawer({
  open,
  view,
  returnFocusRef,
  onClose
}: {
  open: boolean;
  view: TechnicalDetailsView;
  returnFocusRef?: RefObject<HTMLElement | null>;
  onClose: () => void;
}) {
  const drawer = useRef<HTMLDialogElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const node = drawer.current;
    if (!node) return;

    if (open && !node.open) {
      previousFocus.current =
        document.activeElement instanceof HTMLElement
          ? document.activeElement
          : null;
      node.showModal();
      requestAnimationFrame(() => {
        node
          .querySelector<HTMLButtonElement>(
            'button[data-technical-close="true"]'
          )
          ?.focus();
      });
      return;
    }

    if (!open && node.open) {
      node.close();
    }
  }, [open]);

  function finishClose() {
    onClose();
    requestAnimationFrame(() => {
      (returnFocusRef?.current ?? previousFocus.current)?.focus();
      previousFocus.current = null;
    });
  }

  return (
    <dialog
      ref={drawer}
      className="map-technical-drawer"
      aria-labelledby="map-technical-title"
      data-testid="map-technical-drawer"
      onCancel={(event) => {
        event.preventDefault();
        drawer.current?.close();
      }}
      onClose={finishClose}
    >
      <header>
        <div>
          <span className="map-dialog-kicker">HỖ TRỢ / CHẨN ĐOÁN</span>
          <h2 id="map-technical-title">Thông tin kỹ thuật</h2>
        </div>
        <button
          type="button"
          data-technical-close="true"
          aria-label="Đóng thông tin kỹ thuật"
          onClick={() => drawer.current?.close()}
        >
          ×
        </button>
      </header>

      <section>
        <h3>Phạm vi hiện tại</h3>
        <dl>
          <dt>Mã tổ chức</dt>
          <dd><code>{view.organizationId}</code></dd>
          <dt>Mã dự án</dt>
          <dd><code>{view.projectId}</code></dd>
          <dt>Mã bản đồ</dt>
          <dd><code>{view.mapId}</code></dd>
          <dt>Phiên bản cấu hình</dt>
          <dd>{view.configurationRevision}</dd>
        </dl>
      </section>

      <section>
        <h3>Lớp hiện hành</h3>
        {view.activeLayer ? (
          <>
            <dl>
              <dt>Mã lớp</dt>
              <dd><code>{view.activeLayer.layerId}</code></dd>
              <dt>Mã nguồn</dt>
              <dd><code>{view.activeLayer.sourceId}</code></dd>
              <dt>Phiên bản nội dung</dt>
              <dd><code>{view.activeLayer.contentRevision}</code></dd>
              <dt>Phiên bản lược đồ</dt>
              <dd><code>{view.activeLayer.schemaRevision}</code></dd>
              <dt>CRS nguồn</dt>
              <dd>{view.activeLayer.sourceCrs}</dd>
              <dt>CRS lưu trữ</dt>
              <dd>{view.activeLayer.storedCrs}</dd>
            </dl>
            <h3>Khả năng hiện tại</h3>
            <ul className="map-technical-capabilities">
              {view.activeLayer.capabilities.map((capability) => (
                <li key={capability.name}>
                  <code>{capability.name}</code>
                  <span className={"is-" + capability.status}>
                    {capability.label}
                  </span>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p>Chưa có lớp hiện hành để hiển thị metadata kỹ thuật.</p>
        )}
      </section>
    </dialog>
  );
}
