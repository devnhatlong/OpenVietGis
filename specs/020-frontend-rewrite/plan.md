# Implementation Plan: 020 — Frontend Rewrite
**Branch dự kiến**: spec/020-frontend-rewrite | **Date**: 2026-11-22 | **Spec**: [spec.md](spec.md)
**Baseline quan sát**: a5ab44a; trước triển khai cập nhật HEAD, build và evidence.

## Summary
Viết greenfield presentation layer bên cạnh frontend đang hoạt động, reuse SDK/domain/engine có test, không reuse layout và CSS rối. UI mới gồm auth/account, project hub/admin, map workstation desktop, field mobile, module host. Tách backend gap đăng ký/email thành slice có contract và kiểm thử; tránh fork identity.

## Technical Context
- React 19, TypeScript, Vite, React Router, TanStack Query, MapLibre hiện có; ADR-003. Không đổi stack nếu chưa có ADR.
- Design tokens + CSS/Tailwind có giới hạn; chọn primitives accessible sau spike; không cài nhiều bộ component chồng lấn.
- Dữ liệu từ client-sdk/API FastAPI, PostGIS; giữ OIDC+HttpOnly session, CSRF (ADR-013), tenant scope.
- Resend server-side: adapter mail, queue/outbox nếu cần, sender domain xác minh, secret từ runtime secret store; không dùng token ở browser.
- Stage: tạo `apps/web-next/` độc lập hoặc workspace package tương đương qua ADR, chạy preview trên port/route riêng do operator xác định; legacy giữ nguyên. Final cutover versioned artifact.
- Testing: Vitest, Playwright, real Keycloak test realm, API integration, browser visual snapshots, axe candidate, perf baseline.
- Scope: toàn bộ frontend Core + module host + plugin 019; không thay engine/CRS/domain semantics, thêm backend tối thiểu cho auth/mail khi capability gap có evidence.

## Constitution Check
PASS ở cấp thiết kế: module isolation, interoperability, server tenant isolation, CRS explicit, audit revision, command capability, web-native engine boundary, workflow value. Không sửa Constitution. Implementation cần ADR về dual frontend/cutover và onboarding mail trước khi thay backend. Giữ tenant/auth test bắt buộc.

## Project Structure
- `apps/web-next/src/app/`: route, session, providers, errors.
- `apps/web-next/src/ui/`: tokens, primitives, icons, forms, tables and overlay.
- `apps/web-next/src/shells/`: public, hub, studio, field.
- `apps/web-next/src/features/`: auth, onboarding, team, project, layers, inspect, editing, cad, data, jobs, collaboration, plugin.
- `apps/web-next/src/integrations/`: SDK bridge, engine bridge, module registry.
- `apps/api/`: chỉ gap onboarding/email sau contract review; không sửa các domain GIS khác.
- `tests/e2e/frontend-next/`: browser acceptance, screenshot, security, cutover.
- `specs/020-frontend-rewrite/`: bộ hồ sơ hiện tại; [toolchain](toolchain.md), [coverage](coverage.md).

## Delivery
1. Snapshot legacy + route/API/capability inventory. Chốt product map, wireframe, prototype Figma, UI tokens và interaction model.
2. Dựng skeleton preview; identity/team/project là vertical slice thật đầu tiên.
3. Studio map + selection/commands; các chuyên môn theo feature slices.
4. Plugin 019, field offline; inventory closure, accessibility/perf.
5. Stage cùng data fixture, real browser all critical flows, visual review owner, contract/security regression.
6. Build artifact, canary/cutover sau duyệt; rollback artifact cũ, không xóa legacy trước hết thời gian theo dõi.

## Release gates
Không deploy production, gửi mail thật, ghi secret, hay xóa legacy trong giai đoạn đặc tả. Mọi thay đổi auth/mail phải có test non-production. No P0/P1, no unverified UI marked done. Không coi acceptance 016/017 được tự động kế thừa.
