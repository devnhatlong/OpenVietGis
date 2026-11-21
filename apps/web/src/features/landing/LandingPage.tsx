import { Link } from "react-router-dom";

import "../auth/auth.css";

export function LandingPage() {
  return (
    <main className="ovg-landing">
      <a className="ovg-skip-link" href="#main-content">Bỏ qua điều hướng</a>

      <header className="ovg-landing-header">
        <Link className="ovg-brand" to="/" aria-label="OpenVietGIS - Trang chủ">
          <span className="ovg-brand-mark">OVG</span>
          <span>
            <strong>OpenVietGIS</strong>
            <small>Nền tảng GIS web mã nguồn mở</small>
          </span>
        </Link>
        <nav aria-label="Điều hướng trang giới thiệu">
          <a href="#features">Tính năng</a>
          <a href="#workflow">Quy trình</a>
          <Link to="/login">Đăng nhập</Link>
        </nav>
      </header>

      <section id="main-content" className="ovg-hero">
        <div className="ovg-hero-copy">
          <span className="ovg-eyebrow">GIS WEB · POSTGIS · BẢN ĐỒ VIỆT NAM</span>
          <h1>Quản lý dữ liệu không gian trên một giao diện hiện đại, thuần Việt.</h1>
          <p className="ovg-hero-lead">
            OpenVietGIS giúp tổ chức quản lý lớp dữ liệu, bản đồ, biên tập, truy vấn,
            xử lý không gian, nhập/xuất và cộng tác trong cùng một hệ thống.
          </p>
          <div className="ovg-hero-actions">
            <Link className="ovg-primary-link" to="/login">Đăng nhập</Link>
            <a className="ovg-secondary-link" href="#features">Xem tính năng</a>
          </div>
          <div className="ovg-proof-row" aria-label="Năng lực nền tảng">
            <span><b>PostGIS</b><small>Dữ liệu không gian chuẩn</small></span>
            <span><b>MapLibre</b><small>Không gian bản đồ web</small></span>
            <span><b>GeoPackage</b><small>Nhập / xuất dữ liệu</small></span>
          </div>
        </div>

        <div className="ovg-map-preview" aria-label="Minh họa không gian bản đồ OpenVietGIS">
          <div className="ovg-map-toolbar">
            <span>OpenVietGIS</span>
            <span className="ovg-map-status">● Sẵn sàng</span>
          </div>
          <div className="ovg-map-stage-preview">
            <div className="ovg-map-grid" />
            <div className="ovg-map-road ovg-road-a" />
            <div className="ovg-map-road ovg-road-b" />
            <div className="ovg-map-shape ovg-shape-a" />
            <div className="ovg-map-shape ovg-shape-b" />
            <div className="ovg-map-pin ovg-pin-a"><i /></div>
            <div className="ovg-map-pin ovg-pin-b"><i /></div>
            <aside className="ovg-map-layer-card">
              <strong>Lớp dữ liệu</strong>
              <span>☑ Ranh giới khu vực</span>
              <span>☑ Điểm công trình</span>
              <span>☑ Tuyến giao thông</span>
            </aside>
            <div className="ovg-map-coordinates">EPSG:4326 · 10.7769, 106.7009</div>
          </div>
        </div>
      </section>

      <section id="features" className="ovg-feature-section">
        <div className="ovg-section-heading">
          <div>
            <span className="ovg-eyebrow">NĂNG LỰC CỐT LÕI</span>
            <h2>Một workspace GIS cho toàn bộ vòng đời dữ liệu bản đồ.</h2>
          </div>
        </div>
        <div className="ovg-feature-grid">
          <article>
            <span className="ovg-feature-icon">01</span>
            <h3>Quản lý lớp dữ liệu</h3>
            <p>Tổ chức nguồn dữ liệu, lớp hiển thị, CRS, thuộc tính và phiên bản một cách rõ ràng.</p>
          </article>
          <article>
            <span className="ovg-feature-icon">02</span>
            <h3>Không gian bản đồ</h3>
            <p>Làm việc với bản đồ nền, lớp GIS, thuộc tính và lựa chọn đối tượng trong cùng workspace.</p>
          </article>
          <article>
            <span className="ovg-feature-icon">03</span>
            <h3>Biên tập & truy vấn</h3>
            <p>Chỉnh sửa đối tượng, lọc thuộc tính, truy vấn không gian và theo dõi lịch sử thay đổi.</p>
          </article>
          <article>
            <span className="ovg-feature-icon">04</span>
            <h3>Nhập / xuất chuẩn GIS</h3>
            <p>Đưa dữ liệu vào Project, kiểm tra CRS và xuất kết quả qua các định dạng GIS phổ biến.</p>
          </article>
        </div>
      </section>

      <section id="workflow" className="ovg-workflow">
        <div>
          <span className="ovg-eyebrow">QUY TRÌNH</span>
          <h2>Từ dữ liệu thô đến bản đồ dùng chung.</h2>
        </div>
        <ol>
          <li><b>01</b><span><strong>Nhập dữ liệu</strong><small>Đưa dữ liệu vào Project</small></span></li>
          <li><b>02</b><span><strong>Kiểm tra & chuẩn hóa</strong><small>CRS, schema, phạm vi</small></span></li>
          <li><b>03</b><span><strong>Hiển thị & phân tích</strong><small>Bản đồ, truy vấn, xử lý</small></span></li>
          <li><b>04</b><span><strong>Chia sẻ & vận hành</strong><small>Phân quyền, lịch sử, xuất bản</small></span></li>
        </ol>
      </section>

      <section className="ovg-public-cta" aria-labelledby="public-cta-title">
        <span className="ovg-eyebrow">KHÔNG GIAN LÀM VIỆC</span>
        <h2 id="public-cta-title">Sẵn sàng mở OpenVietGIS?</h2>
        <p>Đăng nhập bằng tài khoản đã được cấp để truy cập đúng tổ chức và dự án của bạn.</p>
        <Link className="ovg-primary-link" to="/login">Đi tới đăng nhập</Link>
      </section>

      <footer className="ovg-landing-footer">
        <div className="ovg-brand">
          <span className="ovg-brand-mark">OVG</span>
          <span><strong>OpenVietGIS</strong><small>Nền tảng GIS web</small></span>
        </div>
        <span>© 2026 OpenVietGIS · Xây dựng cho dữ liệu không gian Việt Nam</span>
      </footer>
    </main>
  );
}
