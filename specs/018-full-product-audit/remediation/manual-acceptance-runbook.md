# Independent human acceptance — execution protocol

Status **NOT EXECUTED**. Prepared on 2026-11-22 (Asia/Saigon). This protocol is not an acceptance record and cannot be filled from screenshots, scripted Chromium, developers familiar with the product, or agent simulations.

## Setup (observer/operator)

- Freeze the exact release candidate SHA and selected deployment profile. Use a clean isolated synthetic test tenant and synthetic fixture, not actual customer/cadastral/employee personal data.
- Provision a fresh authorized account and isolated project per attempt, with prepared map, known target feature, saved configuration and independently inspected import fixture/expected export. No training, retrospective selection of participants, or developer assistance.
- Record test date, candidate, browser/device, viewport, fixture SHA, relevant profile/limits, external-network state, and anonymous participant code. Obtain participant consent for observation; do not store real passwords, cookies, tokens or personal identifiers.
- Give only the task prompt; start the timer when the participant receives it and the initial screen is ready; do not stop on partial task completion. Record actual errors, hints requested, and abandonment. Reset fixtures for each independent attempt.
- A failed, interrupted, or assisted attempt is recorded as such; it must not be silently replaced or excluded.

## Tasks and thresholds

| Gate | Participant prompt | Observable success |
| --- | --- | --- |
| R002 SC-013 | Switch to the provided Organization, create a Workspace and Project, then show your membership. | A user with no prior orientation independently completes the four actions in under five minutes. Prior internal-integration exception is not a release waiver. |
| R004 SC-009 | Open the prepared Project, inspect the specified feature, then reopen its saved map configuration. | At least four of five first-time GIS-capable users independently complete it within five minutes; verify the expected feature and restored configuration against fixture/control reads. |
| R005 SC-008 | Import the provided file, check its preview, confirm import; add, view and select its feature, save and reopen the map, download/export the result and locate the CRS/provenance report. | At least four of five first-time GIS-capable users independently complete the whole flow and locate its report. Record actual times and failures; reconcile exported data separately. The criterion itself does not prescribe a five-minute cap. |

The R002, R004 and R005 thresholds above follow the source specifications, not new acceptance conditions. The same first-time user must not be reuse-trained across gates in a way that invalidates first-time status; use independently eligible attempts.

## Observation register (empty until performed)

| Gate | Attempt | Participant code | Candidate SHA | Elapsed seconds | Independent? | Outcome | Failure/hint/fixture evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R002 SC-013 | 1 | pending | pending | pending | pending | NOT OBSERVED | |
| R004 SC-009 | 1–5 | pending | pending | pending | pending | NOT OBSERVED | |
| R005 SC-008 | 1–5 | pending | pending | pending | pending | NOT OBSERVED | |

## Decision boundary

Human acceptance requires genuine observation; software agents can prepare fixtures, run automated tests, independently compare data, and collect measurements, but cannot serve as human participants. Record any scope/profile exception only when explicitly approved by the product owner; retain the original unmet criterion and exact excluded scope. An independent reviewer must verify all source evidence and remaining technical gates on the release candidate. Do not modify release-certification inventory or promote/deploy merely because this runbook exists.
