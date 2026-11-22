# HN019 performance evidence — 2026-11-22

Status: **PASS for the isolated synthetic candidate benchmark; not a production SLA.**

## Candidate and method

- Branch: `feature/019-house-numbering-runtime`.
- Database: dedicated PostgreSQL/PostGIS test database on VPS; production database was not used.
- Runtime: Python 3.13.18, x86_64.
- Module migration includes HN019 search/route indexes in `hn_0003_performance_indexes`.
- Benchmark script: `modules/house_numbering/tests/performance/run_benchmark.py`.
- Dataset is synthetic only.

## Result

| Scenario | Dataset / concurrency | Result |
| --- | ---: | ---: |
| Inspect/numbering on a route | 10,000 buildings | p95 **1.148 s**, median 0.680 s, max 1.148 s |
| Search/query workload | 110,000 buildings + 110,000 numbers | 50 actors, p95 **0.549 s**, max 0.588 s |
| Concurrent wall time | 50 actors | **0.731 s** |
| Acceptance threshold | inspect p95 < 3 s | **PASS** |
| Concurrent result integrity | all actors returned results | **PASS** |

The run produced `/tmp/hn019-performance.json`. These numbers prove the requested synthetic 10k/100k and 50-concurrent-user gate on this VPS candidate only. They do not substitute for production monitoring, data-volume profiling, network latency or customer SLA evidence.
