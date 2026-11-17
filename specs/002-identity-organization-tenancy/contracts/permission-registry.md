# Permission Registry Contract — Spec 002

**Version**: 0.2
**Status**: Planning baseline

Permission codes are stable product contracts. UI visibility, API authorization, future commands, and
modules must request/check permission codes rather than hard-coding role names.

## Organization permissions

| Permission | Meaning |
| --- | --- |
| `organization.read` | Read current Organization metadata and own membership context |
| `organization.manage_members` | Invite, suspend, revoke, or change non-Owner membership within allowed invariants |
| `organization.manage_settings` | Manage non-Owner Organization settings/lifecycle |
| `organization.owner.transfer` | Transfer Owner authority / perform Owner-only ownership transition |
| `organization.delete` | Enter recoverable deleted lifecycle state |
| `authorization.manage_grants` | Create/revoke scoped ResourceGrants |
| `invitation.manage` | Create/revoke invitations |
| `service_principal.manage` | Create/revoke ServicePrincipals and credentials |
| `audit.read` | Read tenant security audit history |

## Workspace permissions

| Permission | Meaning |
| --- | --- |
| `workspace.read` | Read Workspace metadata |
| `workspace.manage` | Create/update/archive/delete Workspace subject to lifecycle invariants |

## Project permissions

| Permission | Meaning |
| --- | --- |
| `project.read` | Read Project metadata |
| `project.edit` | Modify non-management Project metadata/content owned by later capabilities |
| `project.manage` | Manage Project settings/lifecycle within allowed scope |
| `project.move_workspace` | Move/un-group Project only within its owning Organization |
| `project.archive` | Archive/restore Project |
| `project.delete` | Enter recoverable deleted state |
| `project.share` | Manage future-compatible scoped collaboration access; public links remain out of scope |

## Organization role bundles

| Role | Bundle |
| --- | --- |
| Owner | all Spec 002 permissions, including `organization.owner.transfer` and `organization.delete` |
| Admin | all Spec 002 permissions except Owner-only ownership/destructive invariants |
| Member | `organization.read` only by membership role; resource access comes from ResourceGrants |
| Guest | no implicit Organization/resource permissions; explicit ResourceGrants only |

Owner invariants remain domain rules even if a permission code is present.

## Resource role bundles

Resource role bundles are valid at Organization, Workspace, or Project resource scope. Organization
scope grants resource permissions across the tenant but do not grant membership administration.

| Resource role | Bundle |
| --- | --- |
| Manager | `workspace.read`, `workspace.manage`, `project.read`, `project.edit`, `project.manage`, `project.move_workspace`, `project.archive`, `project.delete`, `project.share` as applicable to scope |
| Editor | `workspace.read`, `project.read`, `project.edit`, `project.share` as applicable |
| Contributor | `workspace.read`, `project.read`, `project.edit` as applicable |
| Viewer | `workspace.read`, `project.read` as applicable |

## Evaluation rules

1. Human Organization membership must be active.
2. ServicePrincipal and ServiceCredential must be active/unexpired.
3. All contributing grants must belong to the active Organization.
4. Organization role permissions + Organization resource grants + inherited Workspace grants +
   direct Project grants are a set union.
5. ServiceCredential permission ceiling intersects the ServicePrincipal permission set.
6. No grant subtracts permissions in Spec 002.
7. Cross-Organization Project transfer is not represented by any permission code in Spec 002.
