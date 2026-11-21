# Phase 0 — Candidate research
## Observed evidence (source inspection; not new runtime test)
- VPS candidate c6d449f is 27 commits ahead of main c5cc5a9; active frontend modifications were excluded from this frozen candidate. Keep their ownership separate.
- R006–R015 committed additional migrations 0009–0018, HTTP adapters, persistence and frontend workbenches. Commits 6775287, 7b2cbf7, cb9f75a, bd66f69 are source evidence; counts of added lines do not prove acceptance.
- R007/R008 invoke actual PostGIS spatial predicates, Buffer/Intersection/Union. R009 renderer uses Pillow to produce PNG/PDF. R012 DXF codec uses ezdxf and discloses unsupported entities.
- R006 UI accepts GeoJSON/attribute JSON; interactive graphical map editing must be explicitly reconciled with original approved scope.
- R010 has connection registration, allowlist, invalidation and revocation; no verified provider read/render from inspection. Test actual OGC fixture requests.
- R013 has GeoPackage package/sync APIs; no verified local browser offline persistence or network-loss workflow; distinguish API vs application.
- R015 release-capability list uses static enabled flags. Health/metrics and entitlement storage do not prove effective enforcement or release readiness.
- R006–R015 current spec.md files are short implementation summaries, not exhaustive requirements. Recover prior approved drafts and scope decisions, preserve provenance and mark uncertainty instead of inventing obligations.
- Existing browser test platform-m2-m3.spec.ts tests R006–R009 via workbenches and only readiness/COGO within R010–R015. Existing test-results/.last-run.json reports passed without a pinned manifest. Rerun exact candidate before accepting.
## Decisions
- Use controlled local OGC fixtures, synthetic GIS artifacts, two independent tenant contexts, no real business data.
- Use the existing versioned change model; verify actual side effects and known independent outputs.
- Treat feature readiness, acceptance and release status separately.
- Do not claim complete CAD/Desktop GIS, billing, offline app, or protocol support beyond approved evidence.
