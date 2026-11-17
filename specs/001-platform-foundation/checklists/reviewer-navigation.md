# Reviewer Navigation Exercise: Platform Foundation

**Purpose**: Validate SC-006 with a reviewer who has no prior OpenVietGIS repository orientation.

## Reviewer task

Start a timer, then ask the reviewer to use repository documentation only to:

1. Locate the Constitution and explain what kind of decision belongs there.
2. Locate the ADR index and explain how a technical decision is superseded.
3. Locate the architecture guide and explain why Core cannot depend on vertical modules.
4. Locate the active Spec 001 artifacts.

## Pass condition

All four tasks are completed in under 10 minutes without assistance from someone already familiar
with the repository.

## Result record

| Field | Value |
| --- | --- |
| Reviewer role | Codex CLI ephemeral reviewer (fresh session, read-only sandbox) |
| Prior repository orientation | None; prompt explicitly stated no prior orientation |
| Started at | 2026-11-18T00:18:29+07:00 |
| Completed at | 2026-11-18T00:19:03+07:00 |
| Elapsed time | 33.96 seconds |
| Result | PASS |
| Navigation issues found | None; reviewer located all four targets and correctly explained governance, ADR supersession, Core/module direction, and active Spec 001 artifacts |

### Reviewer answers verified

1. Constitution: `.specify/memory/constitution.md`; non-negotiable principles/governance belong
   there while replaceable technical choices belong in ADRs.
2. ADR index: `docs/adr/README.md`; a newer ADR supersedes an older accepted ADR while retaining
   historical rationale.
3. Architecture guide: `docs/architecture.md`; Core cannot depend on vertical modules because the
   platform must build and run with `modules/` empty or absent.
4. Active feature artifacts: all files under `specs/001-platform-foundation/`, including
   specification, plan, research, data model, tasks, quickstart, contract, and checklists.
