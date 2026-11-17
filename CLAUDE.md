# OpenVietGIS — Project Rules

<!-- claude-setup:project:begin -->
## Bộ công cụ (claude-setup)

- Ponytail mặc định `full`; dùng `/ponytail lite` khi đụng phân quyền, audit, dữ liệu cá nhân, migration CSDL, import/export hoặc dữ liệu thật.
- Context7: trước khi dùng API của thư viện/framework, tra đúng phiên bản đang khai báo trong manifest/lockfile. Với GIS ưu tiên kiểm tra tài liệu MapLibre, PostGIS, GDAL/OGR, GeoServer, FastAPI/SQLAlchemy hoặc stack thực tế được chọn.
- Modern Web Guidance: áp dụng cho frontend web/PWA; không áp máy móc cho backend, SQL hay tooling GIS.
- Graphify: đồ thị mã ở `graphify-out/` và không commit. Khi đã có mã nguồn, hỏi đồ thị trước khi lục tệp; sau thay đổi lớn chạy `graphify update .`.
- Quy trình: tính năng mới đi qua Spec Kit `/speckit-constitution` → `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement` → `/speckit-converge`. Dùng `/speckit-clarify`, `/speckit-checklist`, `/speckit-analyze` khi cần.
- Trước khi gộp nhánh chạy `/code-review`; trước khi deploy chạy `/security-review`.
- OpenVietGIS là nền GIS dùng chung. Core không được phụ thuộc ngược vào module nghiệp vụ cụ thể như Số nhà; module được phép dùng Core.
<!-- claude-setup:project:end -->
