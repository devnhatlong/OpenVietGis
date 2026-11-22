# Research baseline and decisions

- **Observed**: /app mounts SessionBoundary + AppShell + route outlet; 401 redirects /login; LoginPage requests providers and links Keycloak; backend OIDC callback validates transaction and sets HttpOnly app-session cookie. AppDashboard fetches bootstrap, organizations, projects, then hero/cards. AppNavigation uses URL params so menu appears/disappears by project context.
- **Observed**: invitation create/accept/revoke exists at apps/api/openvietgis_api/adapters/http/invitations.py. InvitationAcceptPage currently expects JSON payload; no automatic mail integration verified in inspected code. Do not claim production email or self-registration works.
- **Decision D01**: preserve OIDC authority; brand one provider login entry, use provider-supported registration/reset/verify. Check realm capabilities, email transport and policy in stage, never expose password handling to SPA. Alternative custom password database rejected.
- **Decision D02**: Team invitation via existing server identity/membership service; add server mail adapter and delivery metadata, link handoff. Alternative client sends email rejected.
- **Decision D03**: separate hub and map shell; project name and context persistent. Alternative existing universal sidebar rejected due double navigation.
- **Decision D04**: greenfield UI with existing SDK/engine boundary. Alternative total backend rewrite rejected due GIS correctness/security risks.
- **Decision D05**: one design system, dense desktop controls, accessible primitives; reference QGIS/ArcGIS/AutoCAD and Mobbin for interaction patterns only. Prototype before adding code.
- **Decision D06**: stage side-by-side and retain rollback; no replacement until verified.
- **Open validation (not scope blockers)**: sender domain, realm registration settings, existing invite expiration and email identity semantics, supported module slots, current test inventory, performance baselines, dependency approved versions. Owners resolve in tasks before production. No vendor key in docs.
