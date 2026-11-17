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

<!-- openvietgis:roadmap:begin -->
## Product and roadmap workflow

- Before opening or planning a feature, read `docs/product.md`, `ROADMAP.md`, the Constitution,
  and the relevant Accepted ADRs. Choose a roadmap entry whose required contracts/prerequisites
  are ready; do not invent the next feature solely from its branch number.
- Keep roadmap IDs R001-R015 stable. Future labels 003-015 are provisional capability groups,
  not pre-created specs. Split large groups into linked child slices before implementation.
- Every new feature spec names its parent roadmap and entry ID in Input/summary; update the
  roadmap's feature link, dependencies, stage, and evidence. Existing 001/002 have companion
  `roadmap-reference.md` files; retain those when maintaining traceability.
- Update the roadmap first when scope/dependencies change, then reconcile affected specs/ADRs.
  Product and roadmap documents do not silently amend the Constitution or accepted feature intent.
- Mark done only with implementation, required validation, and convergence evidence. Specify/plan
  completion and task counts alone do not mean the feature or the whole product is complete.
- After contracts are agreed, use separate branches/worktrees with isolated Spec Kit active-feature
  state for parallel implementation. Do not change another agent's active feature, dirty spec/plan,
  or shared branch state to advance an unrelated slice.
- Apply tenant isolation, explicit CRS, attributable changes, validation, recovery and performance
  requirements from the first relevant feature; do not defer their baseline to a later roadmap row.
<!-- openvietgis:roadmap:end -->
