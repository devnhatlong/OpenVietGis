# UI state and integration entities

No new GIS storage model. Canonical server IDs and domain validation are inherited.

| Entity.field | Constraint |
|---|---|
| Session.accountId | Server-confirmed active account only; clear protected cache on 401/account switch |
| Session.status | checking, anonymous, authenticated, degraded, expired; degraded is not anonymous |
| ProjectContext.organizationId | must correspond to authorized resource; workspace/project hierarchy verified server-side |
| ProjectContext.projectId | current authorized project only; before switching check unsaved edits |
| Invitation.email | normalized and verified recipient binding; not leaked to unauthorized actors |
| Invitation.role | server-allowlisted and no escalation beyond inviter authority |
| Invitation.status | pending, accepted, revoked, expired; one-time acceptance |
| MailDelivery.status | distinct from invitation: queued, sent, failed, bounced if provider evidence available |
| MailDelivery.dedupeKey | unique per intended dispatch; retry cannot duplicate membership or silently reissue token |
| WorkspaceSession.selection | scoped to project, layer, revision; invalidated when context changes |
| WorkspaceSession.saveState | clean, dirty, saving, conflict, failed; server confirmation required for clean |
| Command.capability | resolved from permission + engine/source/module capability; deny by default |
| ModuleManifest.slot | registry-approved and enabled per project; Core unaware of business domain |
| UIPreference.scope | account-local or anonymous non-sensitive; never stores tokens or protected payload |
 
Relationships: Account ↔ membership ↔ Organization (Team) → Workspace → Project → Layer. Invitation grants membership only on successful authorized acceptance; delivery does not grant access. ProjectContext owns commands, selection and module slots. UI preference remains independent of shared map configuration.
