import {
  useEffect,
  useRef
} from "react";
import { Link } from "react-router-dom";

import type { AddDataCandidateView } from "./add-data";

export function AddDataDialog({
  open,
  candidates,
  locked,
  importPath,
  catalogPath,
  nextCatalog,
  previousCatalog,
  onAdd,
  onClose
}: {
  open: boolean;
  candidates: AddDataCandidateView[];
  locked: boolean;
  importPath: string;
  catalogPath: string;
  nextCatalog: (() => void) | null;
  previousCatalog: (() => void) | null;
  onAdd: (layerId: string) => void;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const node = dialog.current;
    if (!node) return;
    if (open && !node.open) node.showModal();
    if (!open && node.open) node.close();
  }, [open]);

  return (
    <dialog
      ref={dialog}
      className="map-add-data-dialog"
      aria-labelledby="map-add-data-title"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClose={onClose}
    >
      <div className="map-add-data-head">
        <div>
          <span className="map-dialog-kicker">DỮ LIỆU BẢN ĐỒ</span>
          <h2 id="map-add-data-title">Thêm dữ liệu</h2>
          <p>
            Chọn một lớp đã có trong danh mục hoặc chuyển sang luồng nhập dữ liệu
            chuẩn của dự án.
          </p>
        </div>
        <button type="button" aria-label="Đóng hộp Thêm dữ liệu" onClick={onClose}>
          ×
        </button>
      </div>

      <section aria-labelledby="map-existing-layers-title">
        <div className="map-dialog-section-head">
          <div>
            <h3 id="map-existing-layers-title">Lớp dữ liệu hiện có</h3>
            <p>Chỉ lớp đang được phép và hỗ trợ hiển thị mới có thể thêm.</p>
          </div>
          <div className="map-catalog-pages">
            <button type="button" disabled={!previousCatalog} onClick={() => previousCatalog?.()}>
              Trang trước
            </button>
            <button type="button" disabled={!nextCatalog} onClick={() => nextCatalog?.()}>
              Trang sau
            </button>
          </div>
        </div>

        {candidates.length ? (
          <ul className="map-add-data-list">
            {candidates.map((candidate) => (
              <li key={candidate.layerId}>
                <div>
                  <strong>{candidate.name}</strong>
                  <small>
                    {candidate.geometryFamily} · {candidate.crsLabel}
                  </small>
                  <span className={"map-candidate-status is-" + candidate.availability}>
                    {candidate.availability === "addable"
                      ? "Sẵn sàng"
                      : candidate.availability === "already-present"
                        ? "Đã có trên bản đồ"
                        : candidate.availability === "permission"
                          ? "Không đủ quyền"
                          : candidate.availability === "unsupported"
                            ? "Không hỗ trợ hiển thị"
                            : "Không khả dụng"}
                  </span>
                  {candidate.reason ? <small>{candidate.reason}</small> : null}
                </div>
                <button
                  type="button"
                  disabled={locked || !candidate.addable}
                  onClick={() => onAdd(candidate.layerId)}
                >
                  {candidate.alreadyOnMap ? "Đã thêm" : "Thêm vào bản đồ"}
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <div className="map-dialog-empty">
            <strong>Chưa có lớp dữ liệu trong trang danh mục này</strong>
            <span>
              Bạn có thể nhập dữ liệu mới hoặc tạo lớp từ một nguồn đã đăng ký.
            </span>
          </div>
        )}
      </section>

      <section className="map-add-data-handoff" aria-labelledby="map-new-data-title">
        <div>
          <h3 id="map-new-data-title">Cần dữ liệu mới?</h3>
          <p>
            Luồng nhập/xuất chuẩn sẽ kiểm tra tệp, CRS và tạo lớp trước khi quay
            lại bản đồ.
          </p>
        </div>
        <div>
          <Link className="map-dialog-primary-link" to={importPath}>
            Nhập dữ liệu mới
          </Link>
          <Link to={catalogPath}>Tạo lớp từ nguồn đã có</Link>
        </div>
      </section>
    </dialog>
  );
}
