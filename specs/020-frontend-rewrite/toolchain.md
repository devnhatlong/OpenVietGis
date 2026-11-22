# Frontend Combo Skill — workflow and tool matrix

Use tools to produce reviewable artifacts, not to accumulate plugins. Figma and Product Design connection confirmed 2026-11-22. Mobbin and Modern Web Guidance named by owner; not found as exact available plugins in this session, keep them as optional references until installation verified. Never pretend installed. Do not upload live tenant data/secrets or private GIS records into design tools; use synthetic fixtures.

| Stage | Tool/skill | Expected output |
|---|---|---|
| Product brief | Spec Kit specify/clarify | user journeys, requirements, bounded scope |
| UI research | Mobbin (when available); Product Design; public GIS reference screens | annotated patterns and anti-patterns, no copying proprietary assets |
| UX audit | Product Design | current flow friction, information architecture and screen map |
| Design | Figma (connected) | design tokens, auto-layout components, desktop/field screens, interaction prototype, empty/error variants |
| Design-to-code | Figma design context / Code Connect | component mappings after approval, design evidence, screenshots; not blind code generation |
| Web guidance | Modern Web Guidance (when available); official web/React/MDN/Tailwind docs | responsive CSS, semantics, keyboard, accessibility, performance standards |
| UI engineering | React/TypeScript, Vite, Router, TanStack Query | stable app shell, typed services, route contracts |
| Design system | Tailwind/CSS variables; accessible headless primitives after review; one icon set | tokens, primitives, density, theme, focus; no duplicate library |
| GIS/CAD | MapLibre + existing SDK/engine + test fixtures | command registry, dock model, geometry/CRS correctness |
| Component QA | Vitest, component tests; Storybook optional after dependency review | state matrices, isolated components |
| Browser QA | Playwright + screenshots, browser devtools | real login, project, edit and invitation journeys, console/network evidence |
| Accessibility | axe-core candidate + manual keyboard/contrast | report with 0 critical/serious blockers in flows |
| Performance | browser Performance/Lighthouse candidate, bundle audit | baseline, p95 interaction, startup and regression |
| Security | existing auth/tenant tests, secret scanning, dependency checks | no exposed token, cross-tenant and CSRF tests, release checklist |
| Delivery | Git, existing CI, staging VPS | scoped changes, evidence, rollback; no production cutover without approval |

## Mandatory execution loop
Spec → UX research → wireframe → Figma design/token → review → contract inventory → vertical slice → browser/visual evidence → QA/security/performance → convergence. For each screen provide state coverage (loading, empty, data, error, no access, mobile), scope and API; for every interactive command record functional test. Design changes require update to token/component map. Optional tools may be substituted with equivalent verified tools only; new dependency review required. No fake screenshots, no demo-only happy paths.
