# UI and identity contracts (proposed)

## Routes
Public /; /login single branded entry; /register and /forgot-password route to supported identity provider flows; /invite entry safely resumes after login; /app project hub; /app/projects/:projectId/studio or canonical compatibility project route (decision in route ADR), /app/team management per authorized org; field route remains scoped. Existing /app/organizations/... URLs preserve organization and project scope through canonical mapping; never trust user-chosen return URL outside allowed app origin/path. Error routes: 403, 404, expired invitation.
 
## Session
Anonymous → login (OIDC code + state + PKCE as current) → confirmed app cookie → authorized hub/project. Session refresh background; 401 clears protected cache, no redirect loop. Logout server invalidation; local state cleared. 403 not logout. Login/registration/password recovery use provider-managed credentials; verified email required for bound invitations. No identity tokens in JS storage.

## Invitation and mail
Reuse existing create, accept, revoke endpoints where possible. Add necessary list/resend/delivery contract through SDK review. Create validates authorized inviter, valid role, recipient, creates one pending invitation; server dispatches Resend transactional email via adapter/outbox. Sender and runtime secret configured only server-side. Link: opaque one-time invitation secret, short expiry inherited from server policy, HTTPS; strip token from visible URL promptly, no analytics/referrer/log exposure, no raw JSON entry. Authenticate before accept, recheck exact verified recipient and invite scope. Repeat click idempotent; mismatched/expired/revoked error generic. Resend retry has dedupe, revocation invalidates old token. Deliverability failures are visible to inviter without changing membership. Verify sender domain and test allowlisted recipient prior to live mail. No actual key in source, docs, link, screenshot or browser.
 
## Workstation
One engine session per project; commands registered once and exposed through toolbar/menu/palette/shortcut. Capability/read-only/error states consistent; map selection, layer tree, inspector and table share scoped state. Tool changes preserve view/selection; switching projects clears old data after unsaved guard. Module uses public registry/slots only; field shell offline scoped separately.
