# Requirement and capability coverage (baseline plan)

This is a **tracking plan, not achieved coverage**. Status UNVERIFIED until implementation evidence.

| Prior slice | New surface / test gate |
|---|---|
| 001 platform | app startup, API errors, build/CI |
| 002 identity/tenancy | auth, register, verify, session, team/invitations, cross-tenant |
| 003 spatial | data catalog, CRS/transform, control point evidence |
| 004 map | workstation, layers, selection, viewport, save |
| 005 import/export | validated import/export, open formats, job recovery |
| 006 editing | edit, change history, revision, conflict |
| 007 query | attribute/spatial query and result selection |
| 008 processing | job progress, results and cancel/retry if supported |
| 009 cartography | layout/print/export |
| 010 external | WMS/COG providers and capabilities |
| 011 collaboration | access, review, history |
| 012 CAD | precision, snap, COGO, DXF, verified scope |
| 013 field | field shell, offline scope and sync |
| 014 modules | manifest, activation, slots, permissions |
| 015 readiness | monitoring, performance, recovery |
| 016 shell | replaced UI; retain session and route semantics |
| 017 GIS UX | replaced UI; retain map capability and acceptance |
| 018 audit | reconcile all existing gaps, no false verification |
| 019 house numbering | module UI and actual domain workflow, no Core coupling |

T001 expands every prior FR/SC/acceptance into a row with requirement ID, existing evidence, replacement route/command, test ID, result, evidence path, owner and status. No release with unexplained gaps or P0/P1.
