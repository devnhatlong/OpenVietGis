# HN019 recovery evidence — 2026-11-22

Status: **PASS for isolated synthetic DB + module artifact recovery; external production-readiness gates remain open.**

## Isolation

- Source: dedicated test database `openvietgis_test` in `dev-postgres-test-1`.
- Restore target: `openvietgis_test_hn019_restore`.
- Artifact source: `/tmp/hn019-recovery-artifacts`.
- Restore artifact target: `/tmp/hn019-recovery-restored-artifacts`.
- Production DB/API was not stopped or modified.
- Script: `modules/house_numbering/tests/recovery/run_recovery.py`.

The synthetic module state contained one rule, one route, one building, one approved address number, one import batch, one survey and one official document. The drill also created a public export. DB references existed for the import original, survey photo and official document.

## Result

- DB dump bytes: **192,337,276**.
- DB dump SHA-256: `8c2ef99ec59170629cf483fbb4736374242e31a0e02c6f38af0ed82f27a94cc9`.
- Isolated restore: **PASS**.
- Restore elapsed: **33.895 s**.
- Restored Core Alembic revision: `0019_extension_lifecycle`.
- Restored artifact file count: **8** (4 module artifacts, each bytes + metadata).
- HN scoped DB state before/after: **identical**.
- HN artifact tree before/after: **identical**.
- DB-referenced HN artifacts verified by metadata/byte SHA-256: **3**.
- Restore DB removed after verification: **yes**.
- Restore artifact directory removed after verification: **yes**.

Core restore metadata still reports `authorization_reconciled=false` and `production_ready=false`. This HN drill therefore proves module data/artifact recoverability on the isolated candidate; it does **not** claim the wider platform production-release gate is closed.
