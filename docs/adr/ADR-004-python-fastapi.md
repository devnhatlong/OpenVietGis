# ADR-004: Python Application Backend with FastAPI Adapter

**Status**: Accepted  
**Date**: 2026-11-17

## Context

OpenVietGIS requires a strong spatial processing ecosystem while keeping the main application
backend simple enough for a small team to evolve.

## Decision

Use Python 3.13 as the initial backend baseline. Use FastAPI for HTTP delivery, with Pydantic,
SQLAlchemy 2, and Alembic for initial application infrastructure.

Domain and application services must not depend on FastAPI request/response primitives. HTTP is an
adapter over application behavior.

## Consequences

- The platform can use the mature Python geospatial ecosystem without introducing another primary
  backend language.
- Worker and CLI entry points can reuse application behavior without HTTP emulation.
- Native geospatial dependency compatibility takes priority over adopting the newest Python major
  immediately.
