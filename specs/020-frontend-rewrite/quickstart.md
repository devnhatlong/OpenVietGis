# Verification guide (planned; not evidence of implementation)

1. Record git HEAD and current deployed asset/build ID; list 001–019 acceptance requirements, routes and SDK calls; baseline legacy screenshots and browser performance. Never use production data in fixtures.
2. Start isolated web-next preview with existing API test/stage + Keycloak test realm. Confirm API origin, callback and cookie config. Use synthetic organizations/users; set mail adapter test sink. No live email initially.
3. Once implementation exists run existing root validation and new package lint/typecheck/test/build; run Playwright tests under tests/e2e/frontend-next. Exact commands are recorded by T005 once package created.
4. Browser: register/verify/reset, login/deep link/logout, 401/403/network, invite new/existing/wrong email/expired/revoke/resend, 2 tenant users. Assert API and DB outcomes, not just UI text.
5. Real GIS fixture: load project, add layer, query/edit/revision/undo, import/export CRS, CAD, processing, cartography, WMS/COG, module 019, offline reconnect; record fixture/result IDs sanitized.
6. Capture 1440x900, 1280x800, 768x1024, 390x844; review every priority screen, keyboard, contrast, loading/skeleton/empty/denied/error states. Compare to approved Figma and baseline.
7. Stage smoke email only when sender verified and explicit approved test recipient supplied; record delivery outcome without secret.
8. Run full regression; test rollback using previous artifact and same API, confirm data unchanged; owner approves cutover. Evidence path recorded in coverage.md.
