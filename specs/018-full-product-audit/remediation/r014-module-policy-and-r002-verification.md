# R014 module authority boundary and R002 technical re-verification plan

Source base: `131e103510c74fe749587051dadbe3af75c5c8fd`. Date: 2026-11-22.
This checkpoint is not an approval of a release or a module policy change.
Authoritative R014 first-slice requirements:
`git show 7bb9879:specs/014-module-framework/spec.md` FR-002/003/005/006/007/012/018.
The accepted [ADR-008](../../../docs/adr/ADR-008-module-architecture.md)
requires generic Core and no dependency on a vertical module.

## Existing trust boundary: metadata and Core records, not execution

The current authorization provider resolves the explicit `Permission` enum
(`domains/authorization/permissions.py`) through the fixed Core organization
and resource roles (`roles.py`) and current memberships/grants/credentials.
Service credential ceilings remain subsets of those Core permission IDs.
There is no scoped dynamic extension permission resolver, module-grant table,
installation operator principal or command dispatcher. The namespaced
permissions in a tenant manifest are declarations, not effective grants.
Neither a project grant nor an Owner/Admin role grants installation authority.

The generic extension API registers tenant metadata (current human Owner/Admin),
activates or changes it in a single explicitly authorized project (Core
`project.manage`), and reads/edits typed records with current Core
`project.read`/`project.edit`. These are not module command invocations.
Commands are metadata; not even an owner can execute a declared command
through this API. HTTP request models forbid extra executable, installation
approval, dependency or record-level command fields. A router allowlist test
now locks that boundary in until an authorized implementation design changes
it. Module-specific capability and permission grant semantics remain absent.

Do not infer a permission-to-operation mapping from suffixes (for example
`read` and `write`): the independent reference manifests already include
different business-specific names. Do not give all dynamic permissions to
project managers, treat metadata registration as installation approval, or
silently disable access to existing tenant records. All three would contradict
the original scope.

## Concrete guarded metadata mutation fix

A retained manifest may have been registered before strict
`required_permission`, namespace and version validation. The previous
activation path checked availability and API range only; active create/edit/
import reused that stored record without validating its full manifest contract.
Consequently malformed legacy metadata could still become active or be used
for new tenant record changes. This is not proof of executable code injection:
there is deliberately no dispatcher.

Patch: revalidate the stored manifest with the same bounded contract before
activation, active record create/update/import and version transition (both
old and target manifests). Return `409 EXTENSION_MANIFEST_REVALIDATION_REQUIRED`
before any record/history/lifecycle mutation. Current organization/project
authorization still precedes the check. Disabled or mismatched activation
remains unavailable. Deactivation is allowed for authorized managers even if
stored metadata is no longer valid. Current authorized record reads, history
and portable export remain available; no historical row is rewritten.

This protects old retained data while refusing new changes under an invalid
contract. A valid existing manifest is unchanged. If older metadata is invalid,
preserve and export its data/history; an operator must agree a reviewed
recovery/migration path—no automatic edits or synthesized grants. The web
workbench explicitly labels the current surface as generic Core record
access, not installation approval or command execution.

Pure evidence on the isolated patch: 20/20 tests passed (0.66s), Ruff,
two-source mypy, scope and architecture checks passed. A guarded real PostgreSQL/PostGIS run on the isolated patch passed 7/7
(19.22s, no errors/failures/skips; two dependency deprecation warnings).
Artifact: `/opt/openvietgis-r014-permissions/dist/r014-metadata-guard/real.xml`.
The new real guarded synthetic database test is:
`apps/api/tests/integration/m3/test_independent_lifecycle.py::test_legacy_manifest_mutation_block_preserves_authorized_retained_data`.
It seeds one valid active record, simulates a pre-strict retained command
declaration, then checks activation/mutation/transition refusal, unchanged
record/history, disabled export and outsider denial. It changes only its own
synthetic fixture in a dedicated guarded database. Former valid lifecycle, independent review, generic record contract and both
distinct reference module portability + dual-module workflows passed in the
same guarded run. No production, no services started/stopped by this patch.

## Proposed follow-on policy — owner decision needed before schema/routes

A prospective design for FR-002/003/005/006/007/018 and SC-003, not a
feature that exists today:

1. Installation-controlled immutable registry keyed by module ID, approved
   version, exact contract digest, dependency version constraints, known
   contributions and compatible schema revision. An operator-controlled
   configuration or dedicated privileged installation management mechanism
   (separate from tenancy administrator) may admit an approved fingerprint.
   No tenant endpoint may change this list. Unknown versions, missing
   dependency, cycles, unapproved or changed contract deny runnable state.
2. Register approved permission definition, operation kind, applicable
   scope (organization/project/resource as explicitly supported), required
   capability, module version and contract digest as Core policy data.
   Extend the central effective-permission provider and audit model, not a
   second module authorization engine. Explicit grants to current subject plus
   exact tenant scope, action and contract version; no wildcard implicit
   grants to owners/admins/project editors, and no grant from manifest JSON.
   Integrate service principal ceilings only after the approved grant semantics
   specify that support. A newly added or changed permission defaults denied.
3. Separate tenant activation references installation-approved version and
   explicit current eligible scope. Legacy metadata activations default to
   data-only; do not imply installed or runnable. Preserve ordinary
   Core-authorized archival access and portable export without executing code.
   Existing records remain typed; any schema/data transition is versioned,
   validated and explicit, with preflight and recovery evidence.
4. Only approved internal implementation handlers may be mapped to declared
   command/capability IDs. No arbitrary command, script, SQL, import path,
   module URL or external executable submission. All direct/UI/shortcut/
   deferred entry points share a single scoped decision; check current actor,
   membership/credential, explicit grant, activation version, exact resource,
   supported capability and revisions before execution and again before
   result publication. Revocation or disable after submission denies
   execution/publication; no stale claim or job receipt authorizes a new
   side effect. Reject unsupported processing contribution until R008
   acceptance. Retained archived exports remain a separate Core operation.
5. Validate installation approve/deny independently of tenant Owner/Admin,
   grant/revoke separation, version with new permission default denied,
   command equivalence across entry points, capability mismatch, linked
   resource scope, deferred revocation on execute/publication, dependency
   cycle and failure atomicity, two distinct permitted references and
   Core-only build/run with packages absent. Retain immutable evidence,
   bounded history and migration/recovery matrix. Public SDK gate remains
   independent.

Before implementation, product/security owners must decide **who has
installation authority and by which authenticated mechanism**, approved
module digests/compatibility constraints, which operations require explicit
namespaced grants, grant administrators/subject types/scope granularity,
legacy data-only migration and permission semantics (including retained export),
and audited version/rollback/recovery procedure. No such authority or
semantics may be inferred from organization role names.

## R002 exact current-candidate technical verification

The row audit separately lists prior evidence. Candidate `fabd8c4` real
browser already passed both `tenant-core.spec.ts` scenarios (organization
creation/context switch, tenant URL denial), recorded in the
[row audit index](row-audit-index.md); that pin does not become an exact
new build by assertion. Root executed a fresh guarded API identity matrix on exact base `131e103`.
Initial live-IdP invocation `dist/remediation-final-slice/r002-131e103.xml`
was 76 passed/1 failed of 77 (62.212s, no skip/error). Both real Keycloak
nodes (secret monitor and actual code/PKCE login/logout/stable identity)
passed; non-live redirect assertion hardcoded port 18080 rather than the
explicit isolated 18086 fixture. Standard no-live re-run plus targeted R006
`dist/remediation-final-slice/r002-r006-standard.xml` passed **76/76**
(59.337s, no errors/failures/skips). Do not describe the initial combined
run as green. The browser timing and human gates are separate.

The complete targeted backend corpus, using unique guarded
`OPENVIETGIS_TEST_DATABASE_URL`, synthetic local IdP and artifact directory:

```
uv run --project apps/api --locked --offline python -m tools.run_with_test_database pytest \
  apps/api/tests/integration/identity \
  apps/api/tests/integration/tenancy \
  apps/api/tests/integration/rls \
  apps/api/tests/integration/service_identity \
  --junitxml=dist/<owned-evidence>/r002-full.xml
```

Set `OPENVIETGIS_LIVE_OIDC=1` only with explicitly isolated test realm,
matching discovery/base URLs and reference synthetic test user credentials.
Record 0 skipped for live-provider evidence (or name skips precisely), database
and actual restricted runtime role, commit, fixture and JUnit. Tenant destructive
migration cycles use the repository's fresh loopback disposable fixture;
never run against populated/shared production or another agent's database.
Check exact test-node results for direct database composite foreign keys,
RLS/repository/HTTP scope, connection pool transaction isolation, concurrent
bootstrap/link/unlink/invitation, active last-owner behavior, service principal
ceilings/revocation, actor snapshots, shared/isolated logical fixture parity,
secret non-disclosure. Unit and contract evidence is already mapped in the
row audit; do not promote all requirements from a single green count.

For exact real browser coverage, use the existing guarded Playwright
configuration with **unique** loopback API/Web/OIDC ports (never fallback to
production), explicit database URL and fixture, pinned Node/pnpm and built
SPA. Current scripts (see `package.json` and `playwright.config.ts`):

- Normal initialized synthetic fixture: `tenant-core.spec.ts`,
  `invitation-revocation.spec.ts`, `protected-identity-membership.spec.ts`,
  `tenant-foundation.spec.ts`, `auth-navigation.spec.ts`.
- Independent fresh synthetic fixture via `pnpm validate:e2e:bootstrap`
  (bootstrap config's guarded `--uninitialized` seed). This must not be
  concurrent with the initialized browser or backend suite.
- Timing evidence verifier `tools/check_tenant_timing.py` with both JSON
  reports, secret scanner `tools/check_secret_surfaces.py` against approved
  report/provider logs; redact credentials/raw protected data. Keep exact
  artifact path, pass/fail counts and individual timings; no retaking
  measurements until a desirable sample appears.

Automated nominal SC001 three switches each under 10s, SC004 recipient
acceptance under 180s and SC011 initialized first organization under 300s
have existing canonical test assertions. Their exact evidence is the
attachment metrics, not just test total elapsed time. Bootstrap timing
starts after infrastructure is ready; does not demonstrate full unattended
installation runtime. No agent/browser simulation satisfies SC013
unfamiliar-human observation; retain it as manual/open under the existing
[runbook](manual-acceptance-runbook.md).
