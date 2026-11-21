import { useState } from "react";

import "./frontend-preview.css";

type PreviewView = "overview" | "map" | "data" | "members";

export function FrontendPreviewPage() {
  const [view, setView] = useState<PreviewView>("overview");
  const [tableOpen, setTableOpen] = useState(true);
  const [inspectorOpen, setInspectorOpen] = useState(true);

  return (
    <main className="ux-preview">
      <aside className="ux-preview-sidebar">
        <div className="ux-preview-brand">
          <span>OVG</span>
          <div><strong>OpenVietGIS</strong><small>Frontend DEV Preview</small></div>
        </div>

        <nav>
          <button className={view === "overview" ? "is-active" : ""} onClick={() => setView("overview")}>
            <b>TQ</b><span>Tổng quan</span>
          </button>
          <button className={view === "map" ? "is-active" : ""} onClick={() => setView("map")}>
            <b>BD</b><span>Bản đồ</span>
          </button>
          <button className={view === "data" ? "is-active" : ""} onClick={() => setView("data")}>
            <b>DL</b><span>Dữ liệu GIS</span>
          </button>
          <button className={view === "members" ? "is-active" : ""} onClick={() => setView("members")}>
            <b>TV</b><span>Thành viên</span>
          </button>
        </nav>

        <div className="ux-preview-sidebar-note">
          <strong>UI Preview</strong>
          <span>Dữ liệu mẫu, không ghi vào hệ thống.</span>
        </div>
      </aside>

      <section className="ux-preview-stage">
        <header className="ux-preview-topbar">
          <div>
            <strong>OpenVietGIS</strong>
            <span>/ Dự án Bản đồ Hà Nội</span>
          </div>
          <div className="ux-preview-actions">
            <span className="ux-preview-badge">DEV</span>
            <button type="button">Ctrl K · Lệnh nhanh</button>
            <span className="ux-preview-avatar">NT</span>
          </div>
        </header>

        {view === "overview" ? (
          <section className="ux-preview-page">
            <div className="ux-preview-page-head">
              <div>
                <span className="ux-preview-kicker">KHÔNG GIAN LÀM VIỆC</span>
                <h1>Chào mừng trở lại</h1>
                <p>Quản lý dự án, dữ liệu GIS và các tác vụ đang hoạt động.</p>
              </div>
              <button className="ux-preview-primary" onClick={() => setView("map")}>Mở bản đồ</button>
            </div>

            <div className="ux-preview-metrics">
              <article><small>Dự án</small><strong>4</strong><span>3 đang hoạt động</span></article>
              <article><small>Lớp dữ liệu</small><strong>27</strong><span>24 khả dụng</span></article>
              <article><small>Thành viên</small><strong>8</strong><span>2 quản trị viên</span></article>
              <article><small>Tác vụ hôm nay</small><strong>12</strong><span>10 đã hoàn tất</span></article>
            </div>

            <div className="ux-preview-grid">
              <article className="ux-preview-card">
                <div className="ux-preview-card-head"><h2>Dự án gần đây</h2><button>Xem tất cả</button></div>
                <div className="ux-preview-project-list">
                  <button onClick={() => setView("map")}><span className="dot is-green" /><div><strong>Dự án Bản đồ Hà Nội</strong><small>8 lớp dữ liệu · cập nhật 5 phút trước</small></div><em>Đang hoạt động</em></button>
                  <button><span className="dot is-blue" /><div><strong>Hạ tầng Bình Phước</strong><small>11 lớp dữ liệu · cập nhật hôm qua</small></div><em>Đang hoạt động</em></button>
                  <button><span className="dot" /><div><strong>Quy hoạch khu vực thử nghiệm</strong><small>8 lớp dữ liệu · cập nhật 3 ngày trước</small></div><em>Bản nháp</em></button>
                </div>
              </article>

              <article className="ux-preview-card">
                <div className="ux-preview-card-head"><h2>Truy cập nhanh</h2></div>
                <div className="ux-preview-quick">
                  <button onClick={() => setView("map")}><b>BD</b><span><strong>Mở bản đồ</strong><small>Không gian GIS chính</small></span></button>
                  <button onClick={() => setView("data")}><b>DL</b><span><strong>Dữ liệu GIS</strong><small>Layer, CRS, thuộc tính</small></span></button>
                  <button><b>NX</b><span><strong>Nhập dữ liệu</strong><small>GeoPackage, GeoJSON…</small></span></button>
                  <button><b>CC</b><span><strong>Công cụ</strong><small>Truy vấn, xử lý, in ấn</small></span></button>
                </div>
              </article>
            </div>
          </section>
        ) : null}

        {view === "map" ? (
          <section className="ux-map-workspace">
            <div className="ux-map-toolbar">
              <div><strong>Dự án Bản đồ Hà Nội</strong><small>Đã lưu · Phiên bản bản đồ 2</small></div>
              <div>
                <button>＋ Thêm dữ liệu</button>
                <button>⌖ Phóng tới lớp</button>
                <button>↶ Hoàn tác</button>
                <button className="ux-preview-primary">Lưu</button>
              </div>
            </div>

            <div className="ux-map-grid">
              <aside className="ux-layer-panel">
                <div className="ux-panel-head"><strong>Lớp dữ liệu</strong><button>＋</button></div>
                <label className="ux-layer-row is-active"><input type="checkbox" defaultChecked /><span className="layer-symbol point" /><span><strong>Điểm địa danh Hà Nội</strong><small>Point · EPSG:4326</small></span><button>⋯</button></label>
                <label className="ux-layer-row"><input type="checkbox" defaultChecked /><span className="layer-symbol line" /><span><strong>Ranh giới hành chính</strong><small>Line · EPSG:4326</small></span><button>⋯</button></label>
                <label className="ux-layer-row"><input type="checkbox" defaultChecked /><span className="layer-symbol polygon" /><span><strong>Khu vực quy hoạch</strong><small>Polygon · EPSG:4326</small></span><button>⋯</button></label>
                <div className="ux-layer-add"><button>＋ Thêm lớp có sẵn</button><button>Nhập dữ liệu mới</button></div>
              </aside>

              <div className="ux-map-canvas" role="img" aria-label="Bản đồ mẫu Hà Nội">
                <div className="ux-map-faux-grid" />
                <div className="ux-map-river" />
                <div className="ux-map-road r1" />
                <div className="ux-map-road r2" />
                <div className="ux-map-area a1" />
                <div className="ux-map-area a2" />
                <span className="ux-map-point p1">1</span>
                <span className="ux-map-point p2">2</span>
                <span className="ux-map-point p3">3</span>
                <div className="ux-map-zoom"><button>＋</button><button>−</button></div>
                <div className="ux-map-scale">1 km · EPSG:4326</div>
              </div>

              {inspectorOpen ? (
                <aside className="ux-inspector">
                  <div className="ux-panel-head"><strong>Thông tin đối tượng</strong><button onClick={() => setInspectorOpen(false)}>×</button></div>
                  <div className="ux-inspector-title"><span className="layer-symbol point" /><div><strong>Hồ Hoàn Kiếm</strong><small>Điểm địa danh Hà Nội</small></div></div>
                  <dl>
                    <dt>Tên</dt><dd>Hồ Hoàn Kiếm</dd>
                    <dt>Loại</dt><dd>Danh thắng</dd>
                    <dt>Quận</dt><dd>Hoàn Kiếm</dd>
                    <dt>Trạng thái</dt><dd><span className="ux-status-good">Khả dụng</span></dd>
                  </dl>
                  <details>
                    <summary>Thông tin kỹ thuật</summary>
                    <code>EPSG:4326</code>
                    <code>Feature ID: feature-001</code>
                  </details>
                </aside>
              ) : (
                <button className="ux-inspector-open" onClick={() => setInspectorOpen(true)}>‹</button>
              )}
            </div>

            <div className={tableOpen ? "ux-attribute-table" : "ux-attribute-table is-collapsed"}>
              <div className="ux-table-head">
                <div><strong>Bảng thuộc tính</strong><span>Điểm địa danh Hà Nội · 3 bản ghi</span></div>
                <button onClick={() => setTableOpen(!tableOpen)}>{tableOpen ? "Thu gọn ↓" : "Mở bảng ↑"}</button>
              </div>
              {tableOpen ? (
                <table>
                  <thead><tr><th>STT</th><th>Tên</th><th>Loại</th><th>Quận</th><th>Trạng thái</th></tr></thead>
                  <tbody>
                    <tr className="is-selected"><td>1</td><td>Hồ Hoàn Kiếm</td><td>Danh thắng</td><td>Hoàn Kiếm</td><td>Khả dụng</td></tr>
                    <tr><td>2</td><td>Hồ Tây</td><td>Danh thắng</td><td>Tây Hồ</td><td>Khả dụng</td></tr>
                    <tr><td>3</td><td>Văn Miếu</td><td>Di tích</td><td>Đống Đa</td><td>Khả dụng</td></tr>
                  </tbody>
                </table>
              ) : null}
            </div>
          </section>
        ) : null}

        {view === "data" ? (
          <section className="ux-preview-page">
            <div className="ux-preview-page-head"><div><span className="ux-preview-kicker">DỮ LIỆU GIS</span><h1>Danh mục lớp dữ liệu</h1><p>Quản lý Layer, nguồn dữ liệu, CRS và trạng thái khả dụng.</p></div><button className="ux-preview-primary">＋ Nhập dữ liệu</button></div>
            <article className="ux-preview-card"><div className="ux-data-table">
              <div className="ux-data-row is-head"><span>Tên lớp</span><span>Kiểu</span><span>CRS</span><span>Đối tượng</span><span>Trạng thái</span></div>
              <div className="ux-data-row"><strong>Điểm địa danh Hà Nội</strong><span>Point</span><span>EPSG:4326</span><span>3</span><em>Khả dụng</em></div>
              <div className="ux-data-row"><strong>Ranh giới hành chính</strong><span>LineString</span><span>EPSG:4326</span><span>24</span><em>Khả dụng</em></div>
              <div className="ux-data-row"><strong>Khu vực quy hoạch</strong><span>Polygon</span><span>EPSG:4326</span><span>12</span><em>Khả dụng</em></div>
            </div></article>
          </section>
        ) : null}

        {view === "members" ? (
          <section className="ux-preview-page">
            <div className="ux-preview-page-head"><div><span className="ux-preview-kicker">TỔ CHỨC</span><h1>Thành viên & phân quyền</h1><p>Quản lý người dùng và quyền truy cập theo tài nguyên.</p></div><button className="ux-preview-primary">＋ Mời thành viên</button></div>
            <div className="ux-preview-metrics"><article><small>Thành viên</small><strong>8</strong><span>Đang hoạt động</span></article><article><small>Quản trị viên</small><strong>2</strong><span>Toàn tổ chức</span></article><article><small>Lời mời chờ</small><strong>1</strong><span>Chưa chấp nhận</span></article><article><small>Service actor</small><strong>2</strong><span>Tích hợp hệ thống</span></article></div>
          </section>
        ) : null}
      </section>
    </main>
  );
}
