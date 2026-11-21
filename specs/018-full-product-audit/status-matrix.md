# Initial status matrix — source inspection only
Candidate c6d449fc0ead93e259b79b87e63c1c894bd16c93; rows are provisional; none is newly accepted. Original R001–R003 evidence remains historical, not fresh exact candidate verification.

| R | Capability | Initial observation | Verification pending |
| --- | --- | --- | --- |
| R001 | Foundation | code present; prior accepted | exact CI, restart |
| R002 | Identity/tenancy | prior integration evidence; human gate outstanding | OIDC, two tenants, revocation; manual SC-013 |
| R003 | Catalog/CRS | prior exact CI and controls | regression, independent CRS/identity |
| R004 | Map | UI + backend present | browser workflow, manual SC-009 |
| R005 | Transfer | import/export implementation present | 3 format profiles, round-trip, manual SC-008 |
| R006 | Editing | backend changesets; JSON workbench | approved scope, graphical edit, revision/revert |
| R007 | Query | PostGIS predicates | expected count, selection, permission |
| R008 | Processing | actual SQL Buffer/Clip/Dissolve | independent geometry, jobs/recovery |
| R009 | Cartography | actual PNG/PDF renderer | layout, output quality, scale/CRS |
| R010 | External | metadata/allowlist registration | provider fixture probe/read/render/query |
| R011 | Collaboration | review/activity/rebase endpoints | independent two-user workflows |
| R012 | CAD | ezdxf codec + COGO | roundtrip, loss report, precision controls |
| R013 | Offline | package/sync endpoints | disconnect/reconnect UI, conflict/revocation |
| R014 | Extensions | two reference module implementations | independent lifecycle, boundary/permission |
| R015 | Operations | health/metrics/entitlement; static flags | enforcement, restore, release readiness |
