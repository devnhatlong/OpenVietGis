# Dependency gate assessment — updated 2026-11-22

**Status: HN019 isolated technical candidate verified; external Core promotion gate remains BLOCKED.**

## What changed since the 2026-11-21 assessment

The isolated `feature/019-house-numbering-runtime` candidate now contains and verifies:

- generic R014 official-module discovery, manifest lifecycle, activation/disable and dynamic UI contributions;
- module-owned migration dispatch with no vertical dependency from Core;
- typed House Numbering persistence with revisions, RLS/project scope, audit and protected household access;
- official dynamic module frontend under `modules/house_numbering/frontend`;
- real PostGIS workflows for registry, inspect, numbering preview/apply, proposal approval, imports/reconciliation, survey/progress, documents, search/export and protected data;
- Land Asset coexistence;
- browser, mobile, performance, recovery and security-negative evidence.

Architecture checks pass and the module remains outside Core.

## Gate that is still open

T007 requires proof of the **exact promoted Core baseline** and audit-018 G001/G003/G004/G005/G009/G010. The HN branch cannot truthfully close that organization-wide promotion gate by itself.

Current audit truth:
- G001: exact promoted main/deployment convergence still requires independent proof. The latest isolated SC007 100-open/100-select Core run on `fix/018-confirmed-blockers` still missed the map-open p95 gate: **3352.17 ms** observed vs **3000 ms** required.
- G003: graphical editing acceptance on the promoted Core still requires closure.
- G004: real external-source retrieval/capability acceptance on the promoted Core still requires closure.
- G005: true platform offline client acceptance on the promoted Core still requires closure.
- G009: remediation exists, but must be part of the exact promoted candidate.
- G010: artifact-byte backup/restore remediation exists and HN module recovery passes, but full platform authority reconciliation still reports incomplete.

Therefore integrated HN work is **candidate-verified only** and must not be described as production-released. No production worktree/database was modified by HN019 verification.
