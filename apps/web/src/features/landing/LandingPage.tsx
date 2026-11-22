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
            <small>Studio GIS Web & Không gian số</small>
          </span>
        </Link>
        <nav aria-label="Điều hướng trang giới thiệu">
          <a href="#features">Năng lực</a>
          <a href="#workflow">Quy trình</a>
          <Link className="ovg-nav-cta" to="/login">Đăng nhập →</Link>
        </nav>
      </header>

      <section id="main-content" className="ovg-hero-wrap">
        <div className="ovg-hero">
          <div className="ovg-hero-copy">
            <span className="ovg-eyebrow">OPENVietGIS STUDIO 3.0 · POSTGIS · VN-2000 · AUTOCAD DXF</span>
            <h1>Nền tảng GIS đám mây thế hệ mới cho dữ liệu không gian Việt Nam.</h1>
            <p className="ovg-hero-lead">
              Một studio hợp nhất cho bản đồ vệ tinh & vector, biên tập PostGIS, chuyển đổi bản vẽ
              AutoCAD DXF/COGO, tích hợp WMS/WMTS/COG bên thứ 3 và hệ sinh thái plugin nghiệp vụ.
            </p>
            <div className="ovg-hero-actions">
              <Link className="ovg-primary-link" to="/login">Mở không gian làm việc</Link>
              <a className="ovg-secondary-link" href="#features">Khám phá tính năng</a>
            </div>
            <div className="ovg-proof-row" aria-label="Năng lực nền tảng">
              <span><b>PostGIS + VN-2000</b><small>Chuẩn tọa độ & lịch sử thay đổi</small></span>
              <span><b>AutoCAD & COGO</b><small>Nhập DXF 2D, kiểm tra & trắc địa</small></span>
              <span><b>WMS / COG / Plugin</b><small>Mở rộng nghiệp vụ theo dự án</small></span>
            </div>
          </div>

          <div className="ovg-map-preview" aria-label="Minh họa không gian bản đồ OpenVietGIS">
            <div className="ovg-map-toolbar">
              <span>OpenVietGIS Studio · Hà Nội</span>
              <span className="ovg-map-status">● Trực tuyến</span>
            </div>
            <div className="ovg-map-stage-preview">
              <div className="ovg-map-grid" />
              <div className="ovg-map-road ovg-road-a" />
              <div className="ovg-map-road ovg-road-b" />
              <div className="ovg-map-shape ovg-shape-a" />
              <div className="ovg-map-shape ovg-shape-b" />
              <div className="ovg-map-pin ovg-pin-a" />
              <div className="ovg-map-pin ovg-pin-b" />
              <aside className="ovg-map-layer-card">
                <strong>Lớp dữ liệu GIS</strong>
                <span>● Tuyến phố Hoàn Kiếm (DXF)</span>
                <span>● Điểm địa danh Hà Nội</span>
                <span>● Ảnh vệ tinh Sentinel-2 COG</span>
              </aside>
              <div className="ovg-map-coordinates">EPSG:4326 · 21.0285°N, 105.8542°E</div>
            </div>
          </div>
        </div>
      </section>

      <section id="features" className="ovg-feature-section">
        <div className="ovg-section-heading">
          <div>
            <span className="ovg-eyebrow">HỆ SINH THÁI TOÀN DIỆN</span>
            <h2>Mọi công cụ GIS, CAD và dữ liệu hiện trường trong một nền tảng.</h2>
          </div>
        </div>
        <div className="ovg-feature-grid">
          <article>
            <span className="ovg-feature-icon">01</span>
            <h3>Không gian Bản đồ Web</h3>
            <p>Hiển thị mượt lớp PostGIS trên nền vệ tinh Google/Esri/OSM, bảng thuộc tính và tra cứu tức thì.</p>
          </article>
          <article>
            <span className="ovg-feature-icon">02</span>
            <h3>AutoCAD DXF & COGO</h3>
            <p>Đọc trực tiếp bản vẽ DXF 2D hệ VN-2000, kiểm tra hình học và tính toán tọa độ trắc địa chính xác.</p>
          </article>
          <article>
            <span className="ovg-feature-icon">03</span>
            <h3>Tích hợp Bên thứ 3</h3>
            <p>Kết nối an toàn dịch vụ WMS, WMTS/XYZ, WFS và ảnh vệ tinh COG với danh sách máy chủ kiểm soát SSRF.</p>
          </article>
          <article>
            <span className="ovg-feature-icon">04</span>
            <h3>Biên tập, Phân tích & Plugin</h3>
            <p>Vẽ sửa hình học, Buffer/Clip, in bản đồ PDF và kích hoạt mô-đun nghiệp vụ độc lập theo từng dự án.</p>
          </article>
        </div>
      </section>

      <section id="workflow" className="ovg-workflow">
        <div>
          <span className="ovg-eyebrow">QUY TRÌNH CHUẨN HÓA</span>
          <h2>Từ dữ liệu bản vẽ thô đến bản đồ vận hành thực tế.</h2>
        </div>
        <ol>
          <li><b>01</b><div><strong>Nạp dữ liệu đa nguồn</strong><small>GeoJSON, GeoPackage, Shapefile, DXF 2D hoặc WMS/COG</small></div></li>
          <li><b>02</b><div><strong>Biên tập & Kiểm tra CRS</strong><small>Chỉnh sửa trực tiếp, lưu lịch sử phiên bản và chuẩn hóa tọa độ</small></div></li>
          <li><b>03</b><div><strong>Phân tích & Cộng tác</strong><small>Buffer, Clip, lọc thuộc tính, bình luận và phê duyệt theo vai trò</small></div></li>
          <li><b>04</b><div><strong>Xuất bản & Thực địa</strong><small>In bản đồ PDF, xuất chuẩn GIS và đồng bộ ngoại tuyến hiện trường</small></div></li>
        </ol>
      </section>
    </main>
  );
}
