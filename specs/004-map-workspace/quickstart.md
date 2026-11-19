# R004 validation guide

Status: design, no implementation acceptance evidence yet. Baseline c5cc5a9. Use synthetic dedicated test DB and Keycloak only. Never alter default/production DB or recreate another owner's containers. Local Docker outage: use isolated GitHub CI.

1. Use verified signed Node26 portable path or CI Node26; pnpm install --frozen-lockfile under ordinary release-age policy. No bypass.
2. Run pnpm validate:ts; pnpm validate:py; contract generation/check, scope,architecture,docs guards.
3. Restricted-runtime PostGIS tests: virtual empty map; explicit default revision1; two actors/tenants; reader preview/editor save; edit-only service receipt; CAS/race; same op/same intent; changed/foreign op conflict; precommit rollback; lost acknowledgement after later save; atomic immutable evidence; restart; RLS direct substitution and GUC/pool reuse; archive/delete/suspend/revoke/current ceiling.
4. Viewport: point/line/polygon fixtures and two Layers sharing source; exact4326 display/control geometry,deterministic limits,position/byte/time budgets; partial vs empty vs unsupported/stale; full transformed extent; source counts/IDs/schema/native coordinates unchanged.
5. Browser: Core-only grid/no network workspace surfaces; pan/zoom/fit; order/visibility/style; click/modifier/table selection across pages; out-of-view detail/fit; typed null/empty attributes; default viewpoint preserve/set; save/reopen/two-session conflict; lost-ack unresolved/reconcile; clear renderer/cache/delayed results on context/denial.
6. Benchmark GitHub isolated fixture≤10000 features, desktop1280×900, record runner,Chromium,network disabled,source pins,viewport.5 warmups then100 trials for each open and select→inspector; p95≤3s/1s. Include clear readiness markers after actual renderer/authorized detail completion.
7. Gitleaks committed intended source inventory, exact-SHA full default CI once, independent code review/convergence and docs evidence. No skipped check treated as full success.
8. SC009: five real first-time GIS-capable people, one-sentence task,4/5 independently open/inspect/reopen in5min. Record actual outcomes separately. This remains outstanding until observed; never mark from browser automation. R002 SC013 also remains external-release gate.

Mandatory commands: pnpm validate (full); fixture-safe integration/e2e runners already set by package scripts. Record exact successful SHA/run and actual output here only after execution.
