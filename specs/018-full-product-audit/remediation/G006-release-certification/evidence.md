# G006 runtime verification checkpoint — 2026-11-21

**Candidate**: `d8c692728fe6e1ef6add3eb65a47777d78252259` on `fix/018-release-convergence`; parent 596fb13. No production data, credentials, deployment, merge or original audit mutation. Run on a separate worktree with locked/offline Python dependencies.

## Observations

| Requirement | Layer / action | Expected | Observed |
| --- | --- | --- | --- |
| R015 FR-017–018 / SC-008 | HTTP inventory; real PostgreSQL-backed metrics | Inventory 15; no exact-candidate acceptance or false ready claim | 15 inventory, 0 certified; all unverified; `production_ready=false`; metrics consistent |
| R015 FR-014–015 | Real HTTP dependency readiness | Healthy dependencies not release proof; missing store 503, no creation | Pass; 200 healthy with `scope=dependency_probe_only`; missing-store request 503 and no replacement directory |
| G006 / FR-017 | Unit inventory/metric and CLI release preflight | Static flags, absent review/evidence, wrong profile/candidate and malformed inventory cannot be accepted | Pass; CLI refused release with exit 1 |
| R015 FR-020 / Constitution III, V | Real HTTP entitlement config, owner/member/outsider | Metadata only; authorize config separately, reject invalid IDs and unauthorized writes, retain project, audit actor | Pass; invalid/duplicate IDs 422, member PUT 403, outsider GET/PUT 404, valid owner updates recorded 2 events, project retained after downgrade |
| FR-014 | Unit probe safety | No fixed filename overwrite, symlink or missing root use; sanitized DB failure | Pass; existing probe bytes untouched, no leftover file, clear PostGIS vs DB failure |

## Commands and results

- CPython 3.13.18, lockfile install `uv sync --project apps/api --locked --offline`: passed.
- `uv run --project apps/api --locked --offline pytest -q apps/api/tests/unit/test_ops_release_gate.py tools/tests/test_release_gate.py`: **11/11 passed**.
- `uv run --project apps/api --locked --offline pytest -q apps/api/tests/unit/test_config.py`: **4/4 passed**; includes deliberate rejection of production environment configuration.
- Focused restricted-runtime integration: `python -m tools.run_with_test_database pytest -q apps/api/tests/integration/m3/test_r015_ops_real.py -k r015_production_ops --junitxml=dist/convergence018/r015-g006.xml`: **1/1 passed**, 0 fail/error/skip; 4.771s JUnit suite time.
- Integration target: preallocated synthetic OpenVietGIS test DB on loopback 54332, distinct runtime role, synthetic identity seed, separate configured temporary artifact path. Live OIDC disabled. No production runtime or container changes.
- Ruff and targeted mypy passed; existing contract schema validator, architecture, scope, docs checkers passed. Broad contract/architecture test attempt interrupted before completion (~126/136 visible tests), **not counted**.
- `uv run --project apps/api --locked --offline python tools/check_release_gate.py`: expected exit 1, explicit blocked reasons: missing accepted deployment profile, exact candidate verification, independent record, nine mandatory team capability gates R001–R007/R011/R015.
- `git diff --check`: pass. Ignored JUnit evidence path above; no raw auth material committed.

## Residual release gates

This closes the static false-enabled claim and validates the scoped operational behavior. It does not implement profile acceptance approval, billing, quota enforcement, protected backup profile, approved workload/recovery limits, deployment, later cloud/enterprise parity, full exact-candidate CI or human/reviewer gates. Existing operational health view is dependency-only. The release inventory reports these gates as unverified. The preflight is a structural refusal gate, not independent review. No original 018 requirement is marked globally accepted on this partial checkpoint.
