# Status matrix — exact candidate backend execution and remaining gates

Candidate c6d449fc0ead93e259b79b87e63c1c894bd16c93. No row is fully accepted; individual original FR/SC gates and human/browser acceptance remain distinct. Evidence: [M1](evidence/m1.md), [M2](evidence/m2.md), [M3](evidence/m3.md), [source gaps](evidence/source-gap-review.md).

| R | Capability | Observed exact-candidate evidence | Verification pending |
| --- | --- | --- | --- |
| R001 | Foundation | 8/8 real backend tests | full exact validation and human/CI gates |
| R002 | Identity/tenancy | 77 pass, 1 skip | live OIDC, manual SC-013 |
| R003 | Catalog/CRS | 147 pass; 60 CRS controls; 20 performance scenarios | approved profile/CI traceability and final acceptance |
| R004 | Map | 30 backend pass | browser workflow, manual SC-009 |
| R005 | Transfer | 4 existing backend pass + 9/9 independent round-trip profiles | broader format/CRS negatives, browser/manual SC-008 |
| R006 | Editing | existing changeset/conflict/revert test pass | graphical edit/snapping |
| R007 | Query | existing + independent filter/save/replay assertions pass | scope, negatives, browser |
| R008 | Processing | **BLOCKED G009**: job succeeds but derived feature read fails | canonical output fix and independent geometry rerun |
| R009 | Cartography | real PNG/PDF download, dimensions and colored symbols pass | print layout/scale/legend/visual quality |
| R010 | External | metadata/security existing test pass; **BLOCKED G004**: 4/4 unvalidated provider capability tests fail | fail-closed availability, real adapter retrieval/render/query |
| R011 | Collaboration | review/comment/activity/rebase backend pass | independent two-user workflows |
| R012 | CAD | DXF reader roundtrip/loss + COGO controls pass | full profile/precision breadth |
| R013 | Offline | package download + server sync/conflict/revoke pass | disconnected client local restart and sync |
| R014 | Extensions | reference modules and generic contract tests pass | independent lifecycle and tenant/permission negatives |
| R015 | Operations | health/metrics/entitlement pass; DB restore matches 57,171 features; **G010 backup omits artifact bytes** | full recovery, authority reconciliation, enforcement, release readiness |

Release decision: blocked; G009 reproduced on frozen candidate, plus open source and manual gates. Never promote on green existing-suite count alone.
