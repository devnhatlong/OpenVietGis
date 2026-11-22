# Requirement-row audit: R001, R002 and supplemental R016

Candidate: `9b12310` (exact source commit; isolated worktree). Date 2026-11-22.
This table tracks all **96 frozen rows** assigned from the 656-item original
inventory (R001 28 + R002 68), plus **35 supplemental R016 rows**, not counted
in the original 656. Never update the immutable initial inventory or treat this
as installation/release approval. Source lines refer to the exact immutable
spec versions indicated. Every row describes what was actually checked, what
prior evidence exists and the relevant verification oracle.

## Evidence classes

- **E — exact evidence / open acceptance**: directly relevant test/assertion
  passed on unchanged `9b12310`; broader matrices or historical UI proofs
  remain where stated. A passing unit/targeted test is not proof of every clause.
- **H — historical evidence / exact retest open**: named previous run/source and
  relevant test identified; not asserted equivalent to a new candidate.
- **S — mapped source/oracle only**: implementation/documentation or proposed
  assertion identified, but no independently executed row-specific oracle.
- **G — verified gap**: specific base defect demonstrated; local patch tested
  separately, pending root integration. Never described as fixed in exact base.
- **M — manual/open**: independently observed human exercise required.
- All classes are evidence status, not acceptance labels. **Zero newly accepted
  rows**. Original owner-approved R002 internal integration exception does not
  waive any pre-external release criterion.

| Group | E | H | S | G | M | Rows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| R001 | 8 | 13 | 6 | 1 | 0 | 28 |
| R002 | 55 | 12 | 0 | 0 | 1 | 68 |
| R016 — supplemental, not in 656 | 14 | 19 | 2 | 0 | 0 | 35 |

## Provenance and path notation

Exact 9b12310 independent no-service run: `222 passed`, no errors/failures/skips,
17.28 s, Python 3.13.18 and frozen offline uv environment, identity/tenancy/
authorization unit groups, foundation domain, foundation and identity-tenancy
contract files, architecture and tools suites. This used synthetic configuration
only; no database, provider, browser or network service was started in this
worktree. Raw JUnit/log:
`/opt/openvietgis-row-audit-r001-r002/dist/row-audit-r001-r002/static-9b12310.{xml,log}`.
Exact frontend focused tests: **33 passed** in router, session, AccountMenu,
AppDashboard and protected-query (including actual observer cache transition);
Node 26 and offline frozen pnpm. JUnit/log:
`/opt/openvietgis-row-audit-r001-r002/dist/row-audit-r001-r002/web-9b12310.{xml,log}`.
These are separate invocations; no addition to the full historical suite counts.

Root exact 9b12310 guarded DB suite **50/50**, no errors/failures/skips, 87.274s,
synthetic 54334. JUnit
`/opt/openvietgis-remediation-018/dist/remediation-row-audit/technical-9b12310.xml`.
The exact identity and tenancy nodes were inspected in XML (25 cases:
bootstrap, HTTP security, OIDC redirect/link/unlink, multi-org, invitation
lifecycle, workspace lifecycle, revocation, HTTP access gates and resource
regressions); other nodes include map, import/export, editing and change
evidence. No full database suite or OIDC browser on exact base claimed here.

Historical sources:
- [R001 original quickstart](../../001-platform-foundation/quickstart.md) and
  [R001 tasks](../../001-platform-foundation/tasks.md) (source-only foundation
  bootstrap 3010090, original sample retired later); [frozen R001 DB audit](../evidence/r001.md).
- [R002 original quickstart](../../002-identity-organization-tenancy/quickstart.md)
  final ef731e7 CI 44243951469, timing/secret scan and internal acceptance
  exception; [frozen R002 DB audit](../evidence/r002.md), [M1](../evidence/m1.md).
- [Second integrated remediation](final-next-integration-evidence.md):
  `2b47cc2` full DB run 292 pass, four unrelated-to-R002 failures (test
  manifest and destructive downgrade assumptions), one opt-in OIDC skip,
  exact followup corrected tests at 9261eea, separate real live OIDC at c7bbe62.
  This report explicitly does not call the original full invocation green.
  Identity/tenancy/auth runtime files compared unchanged between its pin and
  9b12310; this assists relevance, not exact-run relabeling.
- [R016 historical quickstart](../../016-app-shell-identity-ux/quickstart.md):
  dbaad69 full prior 31 non-bootstrap + 1 bootstrap Chromium tests passed,
  60 web + 62 SDK; current router/session/shell style has changed and historical
  visual proof cannot substitute for exact rerun.
- [Third integrated R004 evidence](r004-third-integration-evidence.md):
  code-equivalent d1c9c69 browser M1, map and revocation checks. These do not
  cover full identity/shell acceptance.

Path shorthand in rows: **U/** = [API unit tests](../../../apps/api/tests/unit/),
**D/** = [API integration tests](../../../apps/api/tests/integration/),
**W/** = [web app](../../../apps/web/src/app/),
**F/** = [web features](../../../apps/web/src/features/),
**B/** = [browser E2E tests](../../../tests/e2e/).
Use exact named test where supplied; file-level entries mean relevant scenario
family plus remaining oracle, not each assertion proved.

## Verified defect and local remediation

The base `tools/reset_dev.py::main` validates only
`settings.database_url`; [Alembic env.py](../../../apps/api/migrations/env.py)
actually reads `settings.migration_db_url`. Development settings permit
independently supplied migration URL. On exact original 9b12310 source,
mocked `get_settings` with safe local application URI and synthetic
`remote.invalid` migration URI reached the mocked downgrade and upgrade once
each. Both commands were mocked; **no DB contacted, no destructive command
executed**. This is a true unsafe-target validation defect independent of
runtime data.

Local reviewed patch: [tools/reset_dev.py](../../../tools/reset_dev.py)
validates BOTH actual and application URLs and requires identical
host/port/database (distinct credentials allowed), rejects libpq host-address/
service overrides and implicit-port PGPORT overrides before any Alembic call.
New [test_reset_safety.py](../../../apps/api/tests/unit/test_reset_safety.py)
negatives mock both migration commands, asserting neither runs with remote,
other local database/port, query-level or env override; positive same-target
distinct credentials invokes mocked downgrade/upgrade. Local Ruff + targeted
reset/config/test-database/docs suite **52/52 pass** (0.13s). Raw:
`/opt/openvietgis-row-audit-r001-r002/dist/row-audit-r001-r002/reset-and-config.{xml,log}`.
README factual scope drift corrected in the same isolated worktree: current
specs/GIS slices, historical sample retirement, evidence links, supported
bootstrap and safe reset behavior. Source and docs uncommitted for root review;
no permission expansion and no actual destructive reset. Migration 0019's
history rollback refusal stays intact.

## Row inventory

### R001

Source: [frozen requirement inventory](../evidence/requirements.md), source `c6d449f:specs/001-platform-foundation/spec.md`.

| Requirement | Source line | Status | Obligation | Concrete evidence and remaining oracle |
| --- | ---: | --- | --- | --- |
| R001/FR-001 | 144 | H | Reproducible bootstrap | `3010090` clean source checkout 17.91s, pinned prerequisites, warm caches; README/quickstart now corrected. Re-run fresh environment on current candidate; no full boot timed in this audit. |
| R001/FR-002 | 146 | H | Product shell without vertical module | Prior `c7bbe62` M1 real browser read/save/reopen and foundation readiness; actual Core shell in `router.tsx`/`AppShell.tsx`. Build/run with modules physically absent still needs exact runtime check. |
| R001/FR-003 | 148 | H | Persisted UI/domain/repository vertical slice | Historical Spec 001 sample acceptance; retirement `a7c3dcf`/migration 0005 deliberately replaces sample with authenticated tenant Project. R001 audit 8 DB tests; modern `test_tenant_foundation_api.py`, `test_tenant_foundation_repository.py` and `tenant-foundation.spec.ts` oracle. |
| R001/FR-004 | 150 | H | Foundation sample is not final GIS business model | Spec001 history records sample only; 0005 retirement and R002 decision 21. Do not reintroduce deleted sample into current runtime. |
| R001/FR-005 | 153 | H | Restart preserves data before reset | `D/test_tenant_foundation_process_restart.py::test_tenant_record_survives_ten_real_api_process_restarts`, prior c6 audit 10 real processes; exact current retest remains. |
| R001/FR-006 | 155 | S | Document architectural boundaries | `docs/architecture.md`, Constitution, ADR-001/002/008 and `tools/check_architecture.py` explicit dependency direction. `tools/tests/test_docs.py::test_required_documentation_navigation_is_complete` exact run validates navigation, not content accuracy in full. |
| R001/FR-007 | 158 | E | Core can build/run without vertical modules | Architecture `test_core_validation_succeeds_when_modules_directory_is_absent` passed exact static; independent build/run of current physical checkout without modules is separate oracle (not run here). |
| R001/FR-008 | 160 | E | No Core vertical dependency/special case | Architecture `test_rejects_core_to_vertical_module_dependency` and scope synthetic forbidden markers exact static; source guard `tools/check_scope.py`. No exhaustive semantic absence claim. |
| R001/FR-009 | 161 | E | Automated critical dependency check | `tests/architecture/test_architecture.py::test_rejects_core_to_vertical_module_dependency` exact; controlled fixture rejected. |
| R001/FR-010 | 163 | S | Governing principles vs replaceable ADRs | Constitution and `docs/adr/README.md` separately documented; exact docs navigation check. Review accepted ADR status/supersession by reading, not a runtime feature. |
| R001/FR-011 | 165 | S | ADR context/status/date/decision/consequence | `docs/adr/ADR-001` through `014` and index provide record format; no row-specific full ADR-content automated oracle run. |
| R001/FR-012 | 167 | S | Single documented validation workflow | `package.json` `validate` chains runtime/TS/Python/contracts/scope/arch/docs/integration/E2E/security/timing; README documented. Partial exact runs not a complete `pnpm validate` invocation. |
| R001/FR-013 | 170 | E | Validation no production credentials/data | Exact static suite isolated offline; root synthetic dedicated 54334 run. `tools/tests/test_test_database.py` validates safe test configuration. Full exact validation not executed here. |
| R001/FR-014 | 171 | H | Missing prerequisites fail clearly | `D/test_startup_config.py` prior actual process failure; config unit suite in patched local run (config unchanged). Exact current process boot missing-required test pending. |
| R001/FR-015 | 173 | H | Development secrets/private config excluded | Tracked `.env.example` only public fixture; ignored local `.env`; historic R001 Gitleaks zero, R002 CI 44243951469. Exact all-source secret scan/review not run here. |
| R001/FR-016 | 175 | G | Deterministic safe reset/initialization | Verified actual target bug: reset checked application URL, Alembic used separate migration URL. Local fix and mocked no-downgrade regressions pass (see change section); exact base unsafe under mismatched migration configuration. |
| R001/FR-017 | 177 | S | Default branch deployable; experimental work isolated | Candidate is non-main remediation branch and prior integration evidence. No default branch production deploy/promotion verified; release gates remain open. |
| R001/FR-018 | 179 | H | Original scope excludes GIS and verticals | Historical Spec001 task result/runtime guard verified original slice; later separately scoped R003–R015 intentionally implement GIS. No regression claim that current product lacks GIS. |
| R001/FR-019 | 181 | S | Document future boundaries | `docs/architecture.md`, `ROADMAP.md`, Spec001 FR019 and ADR006–012 specify future ownership boundaries; current README facts corrected. Review trace links and contracts. |
| R001/FR-020 | 184 | E | Product-neutral Core terminology | Exact `tools/tests/test_scope.py` rejects vertical markers + architecture guard; original historical sample neutral, current allowed modules isolated. Whole historical docs terminology not re-audited. |
| R001/SC-001 | 203 | H | Clean unfamiliar-contributor bootstrap <20min | Spec001 quickstart 31.5s and exact source `3010090` 17.91s; current fresh environment/reviewer not remeasured. |
| R001/SC-002 | 206 | H | All mandatory foundation checks | Spec001 exact `3010090` root validation documented. Current 222 static + 33 web + root focused DB are partial invocations, not fresh all-green root validation. |
| R001/SC-003 | 207 | H | Ten create/persist/restart/retrieve | R001 audit 8/8 DB at c6, exact `test_tenant_record_survives_ten_real_api_process_restarts` ten subprocesses; historical sample retired, current tenant substitute exact retest pending. |
| R001/SC-004 | 209 | E | Controlled forbidden dependency rejected | Exact `test_rejects_core_to_vertical_module_dependency` and `test_rejects_domain_to_adapter_dependency`; tests use controlled invalid fixtures. |
| R001/SC-005 | 211 | E | Core validation with module absence | Exact `test_core_validation_succeeds_when_modules_directory_is_absent` validates architecture rule only. Physical module-free build/runtime and entire baseline still require independent exact run. |
| R001/SC-006 | 213 | H | Unfamiliar reviewer locates docs <10min | Historical quickstart fresh ephemeral read-only reviewer 33.96s, not a new human or exact candidate exercise; actual reviewer run remains separate. |
| R001/SC-007 | 216 | E | No production access for baseline | Exact offline 222 static and root synthetic DB tests, `test_test_database.py` safe guard. Complete root invocation/historical evidence distinct. |
| R001/SC-008 | 218 | H | Original foundation introduced zero GIS/domain-specific behavior | Historical R001 `tasks.md` scope scan; later separate features allowed. Exact current Core still scope-guarded, no new foundation-only GIS claim. |

### R002

Source: [frozen requirement inventory](../evidence/requirements.md), source `c6d449f:specs/002-identity-organization-tenancy/spec.md`.

| Requirement | Source line | Status | Obligation | Concrete evidence and remaining oracle |
| --- | ---: | --- | --- | --- |
| R002/FR-001 | 264 | E | Human independent of memberships, multi-org | D/identity/test_multi_org_session.py::test_normal_organization_create_requires_initialized_installation_and_creates_owner confirms same user owns >=3 organizations and `/me/organizations` returns them. |
| R002/FR-002 | 266 | E | Stable provider issuer/subject, multiple verified identities | D/identity/test_oidc_login.py::test_identity_link_conflict_and_link_unlink_are_audited; U/identity/test_oidc_link_binding.py current session binding. Actual provider stable login prior c7bbe62 Keycloak. |
| R002/FR-003 | 269 | E | Explicit auditable link/unlink; no email merge | D/identity/test_oidc_login.py conflict/link/unlink audit + U/identity/test_link_conflict_audit.py, test_oidc_link_binding.py independent denial/idempotent. |
| R002/FR-004 | 272 | E | Organization highest ownership boundary | D/tenancy/test_p1_http_access_gate.py::test_foreign_workspace_create_and_move_payloads_are_non_disclosing; test_workspace_project.py cross-org negative. Prior DB composite FK/RLS suite broader. |
| R002/FR-005 | 274 | E | Explicit active tenant context before read | U/authorization/test_repository_context.py::test_required_context_and_foreign_org_rejected_before_sql and raw tenant GUC proof negative, D/tenancy/test_p1_http_access_gate.py. |
| R002/FR-006 | 276 | E | Switch among active memberships | Same multi-org session test returns active memberships without new account; prior measured browser `tenant-core.spec.ts` three context switches. Exact UI timing still unrun. |
| R002/FR-007 | 278 | E | Stable named resources, normal additional org creation atomic Owner | D/identity/test_multi_org_session.py checks rejection before init, two authenticated creates same owner and durable audit; D/tenancy/test_workspace_project.py lifecycle. |
| R002/FR-008 | 285 | E | Workspace/Project direct single Org | D/tenancy/test_workspace_project.py same-org move and foreign reject; prior D/tenancy/test_identity_tenant_migrations.py composite FK and direct lower-level negatives. |
| R002/FR-009 | 286 | E | Optional Workspace grouping preserves owner | D/tenancy/test_workspace_project.py::test_workspace_project_lifecycle_and_same_org_moves; U/authorization/test_repository_context.py::test_explicit_project_ungroup_is_valid. |
| R002/FR-010 | 288 | E | Only same-org Workspace movement | D/tenancy/test_workspace_project.py::test_cross_organization_workspace_move_is_rejected; D/tenancy/test_p1_http_access_gate.py foreign non-disclosing. |
| R002/FR-011 | 290 | E | Ordinary ops cannot change Project owning Org | D/tenancy/test_p1_http_access_gate.py foreign create/move and test_workspace_project.py cross-org; prior `test_project_ownership_boundary.py` actual FK. |
| R002/FR-012 | 293 | H | Cross-org direct ownership references impossible | Prior D/rls/test_cross_tenant_constraints.py and D/tenancy/test_identity_tenant_migrations.py::test_project_workspace_composite_fk_rejects_cross_organization_grouping actual SQL; exact API foreign negative passed, direct FK retest pending. |
| R002/FR-013 | 295 | E | Invitation separate from membership lifecycle | D/tenancy/test_invitation_lifecycle.py recipient binding, optional grant, expired/revoked; D/tenancy/test_p1_http_access_gate.py suspended/revoked next request. |
| R002/FR-014 | 298 | E | Never remove final active Owner | U/tenancy/test_membership_invitation_invariants.py::test_last_owner_downgrade_rejected_while_holding_organization_lock; prior real D/tenancy/test_last_owner.py concurrent role/status tests. Exact concurrency rerun pending. |
| R002/FR-015 | 300 | E | Owner-only lifecycle/destructive vs Admin | U/authorization/test_role_grant_union.py owner/admin distinct; U/tenancy/test_administration_http.py owner-only promotion/revocation, U/tenancy/test_membership_invitation_invariants.py. Prior DB organization lifecycle. |
| R002/FR-016 | 303 | E | Fixed Organization roles and permission bundles | U/authorization/test_role_grant_union.py::test_owner_and_admin_bundles_keep_owner_only_permissions_distinct and `test_member_guest_and_resource_roles_are_additive_capability_bundles`; permission registry docs. |
| R002/FR-017 | 306 | E | Fixed resource roles and Workspace/Project grants | U/authorization/test_role_grant_union.py, exact D/tenancy/test_p1_http_access_gate.py inheritance and additive grants. |
| R002/FR-018 | 309 | E | Permission and scope, not UI visibility | U/authorization/test_authorization_service.py allow/deny and test_repository_context.py scoped proof; D/tenancy HTTP gate direct requests. |
| R002/FR-019 | 311 | E | Permission vocabulary incl share/archive/delete/invite/service | `contracts/permission-registry.md`, U/authorization/test_role_grant_union.py; exact contract suite `test_identity_tenancy_contracts.py`. Exhaustive each action/actor matrix still separate. |
| R002/FR-020 | 315 | E | Shared membership/service principal grant scope | U/authorization/test_repository_context.py effective union and service ceiling unit; prior D/service_identity/test_service_identity_migration.py tenant ownership and grant constraints. |
| R002/FR-021 | 318 | E | Additive permissions, no deny language | U/authorization/test_role_grant_union.py, test_repository_context.py::test_effective_permissions_union_multiple_grants_without_decision_cache; D/tenancy/test_p1_http_access_gate.py inheritance. |
| R002/FR-022 | 321 | E | Guest no implicit org-wide visibility | U/authorization/test_role_grant_union.py member/guest distinction; prior D/rls/test_cross_tenant_api.py direct access and D/tenancy/test_tenant_error_semantics.py; exact complete guest matrix pending. |
| R002/FR-023 | 323 | E | Invitation entity target Org/role/status/expiry, optional grant separate | D/tenancy/test_invitation_lifecycle.py::test_invitation_recipient_binding_accept_once_and_optional_grant; contract tests. |
| R002/FR-024 | 327 | E | Invite one-time, expiry/revocation/use denial | D/tenancy/test_invitation_lifecycle.py direct tests both service and runtime; prior `test_invitation_concurrency.py` exact-once concurrency. |
| R002/FR-025 | 329 | E | Verified internal user membership, not email as identity | D/tenancy/test_invitation_lifecycle.py tagged email/user/external_identity cases; U/tenancy invitation binding tests. |
| R002/FR-026 | 331 | E | Invitation secret unrecoverable | U/identity/test_secrets.py generation/hash/verify, source `SqlTenancyRepository` stored digest; `tools/tests/test_secret_surfaces.py` scan regression. Prior secret-surface/browser audit; actual exact persisted no-plaintext check distinct. |
| R002/FR-027 | 333 | E | Suspend/revoke denies next protected action | D/tenancy/test_revocation.py and `test_p1_http_access_gate.py::test_http_membership_suspension_or_revocation_denies_next_request[suspended/revoked]` on same session exact. |
| R002/FR-028 | 335 | E | Consistent product authorization boundary across actors | U/authorization/test_authorization_service.py and test_context.py + test_repository_context.py, prior D/service_identity/test_service_authorization.py. Background worker execution not in R002. |
| R002/FR-029 | 337 | E | Lower-level cross-org read/mutation denied | U/authorization/test_repository_context.py before SQL, exact direct HTTP foreign denial; prior D/rls/test_cross_tenant_repository.py/constraints/pool. Exact full lower-level corpus pending. |
| R002/FR-030 | 339 | E | Serializable requested-actor context envelope, no cached grants | U/authorization/test_context.py three round-trip tests human/service credential/system; no background worker required. |
| R002/FR-031 | 343 | E | Organization/Workspace lifecycle and soft recovery | U/tenancy/test_workspace_lifecycle.py and membership invariant inactive org, exact D/tenancy/test_workspace_project.py lifecycle; prior D/tenancy/test_organization_lifecycle.py/test_deleted_recovery.py. |
| R002/FR-032 | 349 | E | Project active/archive/deleted; read-only archived | D/tenancy/test_workspace_project.py lifecycle and D/tenancy/test_p1_resource_regressions.py archive restore negative; exact map auth archive read and no edit. |
| R002/FR-033 | 352 | E | Nonhuman Service Principal cannot human login | U/identity/test_service_credentials.py explicit principal status and service credential contract; `authenticate_request` service route requires Org ID; D/service_identity/test_service_authorization.py prior. Exact interactive-negative live provider not run here. |
| R002/FR-034 | 354 | E | Service belongs one Org, explicit grants only | U/authorization/test_service_permission_ceiling.py and role-grant context; prior actual D/service_identity/test_service_identity_migration.py composite constraints. |
| R002/FR-035 | 356 | E | Service usable secret only at creation, hash metadata persists | U/identity/test_service_credentials.py actual token/hash verification, malformed rejected, U/authorization/test_audit_redaction.py; prior actual P2 secret surfaces. |
| R002/FR-036 | 359 | E | Service expiry/revocation immediate | U/identity/test_service_credentials.py::test_service_credential_expiry_and_revocation_are_immediate and exact runtime D/maps/test_authorization_matrix.py edit-only service. Prior D/service_identity/test_service_authorization.py. |
| R002/FR-037 | 361 | E | Audit stable actor, Org, historical display after revocation | Exact D/spatial/test_change_evidence.py service snapshot after revoke (later R003 reuse); D/identity/test_oidc_login.py audit; prior D/service_identity/test_audit_actor_snapshot.py. |
| R002/FR-038 | 364 | E | Audit human/service/system distinction | U/authorization/test_context.py actor type roundtrips and audit redaction; prior actual actor snapshot/P1/system bootstrap audit; exact full three actor matrix pending. |
| R002/FR-039 | 365 | E | Fresh self-host one-time explicitly authorized bootstrap | D/identity/test_bootstrap.py::test_bootstrap_requires_session_and_authority_and_commits_once checks anonymous/session/secret/CSRF, committed Owner and reuse. |
| R002/FR-040 | 370 | E | Bootstrap authority becomes unusable after setup | Same exact bootstrap test reuse 409, prior `test_bootstrap_concurrency.py` one winner and `test_bootstrap_storage.py` immutable install-state transition. |
| R002/FR-041 | 373 | H | Shared & isolated deployment logical parity | D/tenancy/test_isolated_deployment_parity.py::test_same_domain_and_contracts_in_shared_and_isolated_deployment_fixtures passed prior full DB suite. No production isolated deploy required. |
| R002/FR-042 | 377 | H | Minimal UI for switch/membership/create/invitation/revoke | Browser tenant-core + invitation-revocation and protected-identity-membership historical. Exact current `AppDashboard.test.tsx` supports names but not full user workflow. |
| R002/FR-043 | 380 | E | No public or anonymous share links | Exact tools scope negative marker `publicsharelink`, actual protected access in `test_p1_http_access_gate.py`; source route inventory/auth contract no public share endpoint. Full semantic negative review remains. |
| R002/FR-044 | 381 | E | No custom role creation | Exact `tools/tests/test_scope.py` guard rejects `customrolebuilder`, fixed role test and API contracts. Future roles deliberately out of scope. |
| R002/FR-045 | 382 | E | Sensitive ownership/grants/invitation/credential/bootstrap actions auditable | Exact multi-org audited IDs, identity conflict, invitation lifecycle and bootstrap; U/audit redaction. Prior D/tenancy/test_p1_audit_mutations.py and D/service_identity/test_audit_actor_snapshot.py broader. |
| R002/FR-046 | 384 | H | R002 original future Layer/Map/module boundaries | Original R002 architecture/contracts/quickstart; R003+ later scoped product features are not violations. Exact architecture/scope static guards continue. |
| R002/FR-047 | 387 | E | Org/Workspace/Project grant scopes; movement invalidates inherited grants | D/tenancy/test_p1_http_access_gate.py::test_http_workspace_inheritance_tracks_project_moves_without_grant_copying, U/authorization effective union test; prior repository inheritance tests. |
| R002/FR-048 | 394 | E | Human resolves external identity→internal user→active membership/context/permissions | D/identity/test_oidc_login.py, D/identity/test_http_security.py cookie auth and CSRF, D/tenancy next action revocation, U/repository context unauthorized raw proof. |
| R002/FR-049 | 397 | E | Invite recipient verified identity/email, not secret alone | Exact D/tenancy/test_invitation_lifecycle.py::test_runtime_accepts_only_matching_invitation_recipient[email/user/external_identity] plus U/tenancy exact current issuer/subject and email verification. |
| R002/FR-050 | 401 | E | Current lifecycle/grants/workspace placement and credentials each protected action | Exact D/tenancy/test_p1_http_access_gate.py revoke/inherit tests and U/authorization no decision cache; prior real service stale lookup and ceiling. |
| R002/FR-051 | 404 | E | Human tenant core independently usable | Exact D/identity/test_multi_org_session.py normal org, D/tenancy/workspace/invitation/revoke independently human; prior browser tenant-core. Bootstrap only prerequisite install, no service actor need. |
| R002/FR-052 | 408 | E | Unique stable external identity conflicts rejected/audited | D/identity/test_oidc_login.py actual conflict link/unlink; U/identity/test_link_conflict_audit.py, prior SQL uniqueness/concurrent identities callback test. |
| R002/FR-053 | 411 | E | Cannot delete Workspace with active Project | D/tenancy/test_workspace_project.py::test_workspace_delete_rejects_active_project; U/tenancy/test_workspace_lifecycle.py; archived-project deleted-Workspace restore regression. |
| R002/FR-054 | 414 | E | Credential ceiling restricts only principal grants | U/authorization/test_service_permission_ceiling.py two tests; prior real service auth scoped ceiling + exact new D/maps service edit-only/read denial. |
| R002/SC-001 | 465 | H | Three org switches <10s, same session | Prior exact ef731e7 browser `tenant-core.spec.ts` timed 193/192/149ms; exact 9b12310 multi-org API demonstrates same internal user, not UI stopwatch. Re-run canonical browser timing. |
| R002/SC-002 | 468 | H | All defined R002 cross-org read/mutation negatives denied | Prior complete actual D/rls suite and c6 R002 77 pass/one live skip; exact targeted D/tenancy foreign moves + grant negatives. Exact full matrix RLS/API/repository/constraints still pending. |
| R002/SC-003 | 471 | E | Suspend/revoke next action denied in all tests | Exact D/tenancy/test_revocation.py and P1 same-session both suspended/revoked tests pass. Prior performance benchmark. Wider all tests exact rerun pending if required. |
| R002/SC-004 | 473 | H | Valid invitation accepted/scoped access <3 min | Prior ef731e7 browser measured 903ms from defined acceptance start, recipient binding and grant; exact DB acceptance verifies security not timing. Re-run real browser. |
| R002/SC-005 | 475 | E | All expired/revoked/used invite negatives | Exact all D/tenancy/test_invitation_lifecycle.py tests pass incl `[expired]`, `[revoked]`, repeat use and target mismatch; prior concurrent acceptance. |
| R002/SC-006 | 477 | E | Final Owner invariant all tested transitions | Exact U/tenancy/test_membership_invitation_invariants.py last-owner and admin restrictions; prior D/tenancy/test_last_owner.py concurrent runtime. Exact full DB invariant retest pending. |
| R002/SC-007 | 479 | E | Same-org moves and ungroup retain ID/Org in lifecycle tests | Exact D/tenancy/test_workspace_project.py::test_workspace_project_lifecycle_and_same_org_moves; same-session inheritance test. |
| R002/SC-008 | 482 | E | No cross-org move in transfer-boundary tests | Exact cross-Org D/tenancy/test_workspace_project.py and P1 foreign create/move; prior direct DB composite FK. |
| R002/SC-009 | 484 | H | Service scoped permitted/denied, revoked immediately | Prior actual D/service_identity/test_service_authorization.py all cases and R002 c6 service 11/11. Exact unit ceiling and map service regression; full exact service actions not run here. |
| R002/SC-010 | 486 | H | All sensitive flow audit actor types/org retained after revoke | Prior actual D/service_identity/test_audit_actor_snapshot.py, test_audit_storage.py, D/tenancy/test_p1_audit_mutations.py; exact scoped R003 change audit service snapshot. Full R002 exact corpus pending. |
| R002/SC-011 | 489 | H | Fresh self-host bootstrap <5min and reuse denied | Prior ef731e7 `bootstrap-service-identity.spec.ts` 1,019ms documented measured bootstrap flow, not full infra provisioning; exact API session/secret/CSRF and reuse pass, current bootstrap browser not timed. |
| R002/SC-012 | 492 | H | Shared/isolated logical fixture parity | Prior actual `D/tenancy/test_isolated_deployment_parity.py::test_same_domain_and_contracts_in_shared_and_isolated_deployment_fixtures`; exact run remains. |
| R002/SC-013 | 496 | M | Unfamiliar human completes minimum flow <5min | Owner internal-integration exception does not waive external gate. Use manual-acceptance-runbook with genuinely uncoached unfamiliar person; no synthetic substitute, no result. |
| R002/SC-014 | 499 | H | Original R002 introduces zero public share/custom roles/GIS feature | Historical original R002 scope+CI static/contract boundaries, current exact scope marker tests; subsequent R003–R015 implement separately authorized GIS. Original feature scope, not a claim current product lacks GIS. |

### R016 — supplemental, not in 656

Source: [current source spec](../../016-app-shell-identity-ux/spec.md), candidate `9b12310`.

| Requirement | Source line | Status | Obligation | Concrete evidence and remaining oracle |
| --- | ---: | --- | --- | --- |
| R016/FR-001 | 111 | H | Public landing / independent of auth | B/auth-navigation.spec.ts::public landing and dedicated login are separate surfaces; prior R016 dbaad69 browser. Route `/` not wrapped in SessionBoundary; exact current browser not run. |
| R016/FR-002 | 112 | H | Dedicated /login, no scrolling landing | Same historical browser plus `LoginPage.tsx` route and dedicated heading/action. Exact smoke on current split route pending. |
| R016/FR-003 | 113 | E | Protected return destination, successful auth returns | Exact W/session/return-destination.test.ts safe relative/external negative; SessionBoundary 401 return; prior real B/auth-navigation.spec.ts deep-link OIDC return. |
| R016/FR-004 | 114 | E | Canonical /app human-readable dashboard | Exact F/dashboard/AppDashboard.test.tsx name cards and empty state + router contract. Actual browser journey historical. |
| R016/FR-005 | 115 | H | Persistent scope-meaningful primary navigation | `AppNavigation.tsx`/`navigation-model.ts` scope items Overview, Projects, GIS, Map, Tools, Members; B/app-shell.spec.ts across org/project navigation prior. Exact browser role/scope matrix remains. |
| R016/FR-006 | 116 | H | Persistent account/session/invite/logout across major surfaces | `AppShell.tsx` includes AccountMenu; B/app-shell.spec.ts and B/auth-navigation.spec.ts deep route logout prior. Exact all major surfaces matrix pending. |
| R016/FR-007 | 117 | H | Signout invalidates session/protected request | Prior actual live `D/identity/test_live_keycloak_oidc.py::test_live_keycloak_code_pkce_login_logout_and_stable_identity` and B/auth-navigation.spec.ts signout deep route/next unauthenticated response. Exact D/identity/test_http_security.py cookie auth and CSRF, not logout; exact current click/revocation replay pending. |
| R016/FR-008 | 118 | E | Background validation keeps known authenticated shell mounted | Exact W/session/SessionBoundary.test.tsx retained visible shell while fetching, session-state unit. Prior B/app-shell.spec.ts background /me revalidation actual browser. |
| R016/FR-009 | 119 | E | Auth loss routes login and hides protected data | Exact W/session/SessionBoundary.test.tsx 401 redirect and W/protected-query-cache.test.ts actual warm cache fetch/denial, `protected-query.test.ts` statuses. Prior protected identity browser. |
| R016/FR-010 | 120 | E | Readable organizations/projects/actions, not UUID | Exact F/dashboard/AppDashboard.test.tsx rendering human names without primary IDs; source `Breadcrumbs.tsx` labels. Browser prior. |
| R016/FR-011 | 121 | H | Technical identifiers/revisions hidden from ordinary workflow | R016 B/app-shell.spec.ts, F/dashboard/AppDashboard.test.tsx known names, current technical details drawers R017. Full ordinary-flow identifier audit needs exact browser review. |
| R016/FR-012 | 122 | E | Permission/capability affordances not enforcement | Exact W/protected-query.test.ts and actual observer cache denial, D/tenancy authority and role suite. B/protected-identity-membership.spec.ts historical permission revalidation; full control-level UX matrix still needs browser. |
| R016/FR-013 | 123 | S | Absent permission vs unsupported capability communicated distinctly | Map `layer-view.ts`/`add-data.ts` and command capability semantics provide this distinction; generic shell nav uses scope not effective permissions. Need exact multi-surface role/capability presentation oracle; no claim full coverage. |
| R016/FR-014 | 124 | H | Vietnamese-first shell, technical terms allowed | Source Landing/Login/AppDashboard/AppNavigation labels Vietnamese, B/app-shell visual and historical terminology acceptance. Exact terminology scan/reviewer required. |
| R016/FR-015 | 125 | H | No raw backend enum/roadmap/dev labels ordinary UI status/navigation | F/dashboard/AppDashboard role/status translation + prior B/app-shell visual/terminology. Exact entire ordinary surfaces audit pending. |
| R016/FR-016 | 126 | E | Clear loading/empty/error/success, no alert dialogs | Exact F/dashboard/AppDashboard no-project and boot gate, W/session/SessionBoundary pending/auth loss; LoginPage error state source. Historical browser; not all shell states exact. |
| R016/FR-017 | 127 | H | Keyboard focus and accessible names | B/app-shell-accessibility.spec.ts skip/focus/touch targets prior; CSS `:focus-visible`, named navigation/AccountMenu. Exact browser keyboard matrix across primary surfaces pending. |
| R016/FR-018 | 128 | H | Responsive desktop/tablet, no horizontal overflow | B/app-shell-accessibility.spec.ts explicit widths 768/1024/1440 prior; current responsive CSS/lazy route changes merit exact browser rerun. |
| R016/FR-019 | 129 | E | Safe legacy URL redirects preserve context | Exact W/router.test.tsx org/project/static routes, source router redirects; B/app-shell.spec.ts legacy organization route historical. Exact all redirect journeys not browser-executed. |
| R016/FR-020 | 130 | S | Local shell preferences separate shared configuration | `apps/web/src/app/shell/shell-preference.ts` stores collapse preference separate from server map config. No specific exact R016 persistence/invariance test; add browser close/reopen and unchanged map revision check. |
| R016/FR-021 | 131 | E | Existing identity/authorization semantics, no client-owned auth model | Exact D/identity/tenancy authority cases + W/protected-query-cache.test.ts and SessionBoundary use server `/me`; UI never grants. Prior browser role revocation. |
| R016/FR-022 | 132 | H | No OIDC access/ID tokens stored in browser storage | `LoginPage.tsx` uses server OIDC redirect, `SessionBoundary` gets CurrentUser; auth client stores CSRF in memory; no local/session provider tokens in source. Prior live OIDC/browser storage secret scan, exact runtime secret monitor separate. |
| R016/FR-023 | 133 | E | Existing CSRF/session for unsafe mutations | Exact D/identity/test_http_security.py cookie/session CSRF, U/identity/test_csrf.py token bound; AccountMenu loads CSRF before logout, source mutation wrappers. Browser historical. |
| R016/FR-024 | 134 | H | Coherent light theme; no dark mode required | Shared `app-shell.css`, global theme and public styles; prior deterministic B/app-shell-visual.spec.ts baselines. Comparison on exact current built CSS pending. |
| R016/FR-025 | 135 | H | Consistent OpenVietGIS brand; denser authenticated workspace | Landing/Login brand and AppShell visual source, prior B/app-shell-visual.spec.ts snapshots. Current source review mapped but visual exact pending. |
| R016/SC-001 | 150 | E | All tested valid-session focus/refetch shell transitions retain mount | Exact W/session/SessionBoundary.test.tsx one SSR controlled refetch + session-state unit; B/app-shell.spec.ts independently actual browser focus revalidation on dbaad69. Exact browser denominator not rerun. |
| R016/SC-002 | 151 | H | One intentional action Landing→Login→Landing | B/auth-navigation.spec.ts prior separate surfaces/direct action. Exact current smoke pending. |
| R016/SC-003 | 152 | E | One organization identify/open project without UUID | Exact F/dashboard/AppDashboard.test.tsx name cards; prior B/app-shell.spec.ts projects real browser navigation. Need exact actual click journey. |
| R016/SC-004 | 153 | H | Logout within two interactions each major screen, then unauthenticated | Prior B/auth-navigation.spec.ts actual deep route logout and live Keycloak server test; AccountMenu always available via AppShell. Exact D/identity cookie/CSRF pass, not logout itself; complete current screen matrix pending. |
| R016/SC-005 | 154 | H | Keyboard-only all primary shell interactions visible focus | B/app-shell-accessibility.spec.ts prior skip/navigation/focus. Full all controls current browser or manual keyboard observation needed; no simulated human assertion. |
| R016/SC-006 | 155 | H | No page overflow at >=768 reference widths | B/app-shell-accessibility.spec.ts prior explicit 768/1024/1440 widths; current visual viewport exact remeasure. |
| R016/SC-007 | 156 | H | Deterministic four screenshot baselines no unexplained diff | Historical dbaad69 screenshots Landing/Login/Dashboard/Account Menu pass; same `tests/e2e/app-shell-visual.spec.ts` stored baseline. Router/lazy CSS changed; exact current comparison mandatory. |
| R016/SC-008 | 157 | E | Tested legacy URL set preserving IDs/context no deadends | Exact W/router.test.tsx maps org/project/static legacy paths; prior B/app-shell.spec.ts browser legacy org. Exact browser complete route set pending. |
| R016/SC-009 | 158 | H | Terminology audit ordinary Landing/Login/Dashboard/nav no raw codes/enums | Historical R016 convergence screenshot/terminology check; current source labels reviewed and dashboard tests. Exact current ordinary-content terminology oracle not executed. |
| R016/SC-010 | 159 | E | Existing server tenant/auth regressions; frontend not authority | Exact 222 identity/tenancy/authorization/contract/static + root 50/50 targeted DB; exact W/protected-query-cache deny warm result. Full server matrix from prior integrated runtime, not all exact current. |

## Remaining priority

1. Root's broader exact R002 DB matrix (RLS API/repository/SQL/pool, service
   scopes/credential revoke, last Owner and invitation/identity concurrency,
   lifecycle, isolated fixture parity, audit and authorization benchmark)
   must be checked with guarded synthetic DB. Historical coverage exists; exact
   new run evidence must not be inferred from test collection.
2. Run real isolated Keycloak/browser R002 technical journeys on integrated
   candidate, including timed three-organization switch, invitation acceptance,
   first-owner bootstrap, logout/session/CSRF and current revoked read. The
   previous timed evidence remains valid for its source pin only.
3. Exact R016 browser suite: focus/refetch no flash, deep-link and logout,
   scope navigation/accessibility/widths/terminology and all four deterministic
   screenshot comparisons. Do not automatically update screenshots to mask a
   visual regression.
4. Real unfamiliar-user observation for original R002 external acceptance and
   separately required release gates remains open. No agent stopwatch or
   synthetic browser journey substitutes for a person. See
   [manual acceptance runbook](manual-acceptance-runbook.md).
