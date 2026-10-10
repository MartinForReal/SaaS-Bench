# Fast Provisioning Measurement Slice

## Purpose

Measure provisioning readiness without mutating a slot, so prewarmed-pool,
snapshot/PVC, and operator-managed DB improvements can be compared with evidence.

## Tooling

- `saas_bench/provisioning_metrics.py`
  - pure helpers for pod-ready latency, percentile summaries, PVC binding, and
    fast-provisioning readiness
- `scripts/measure_provisioning.py`
  - read-only kubectl wrapper that writes a JSON snapshot for one namespace
- `tests/test_provisioning_metrics.py`
  - unit coverage for latency math and readiness summaries

## Measured Evidence

Slot 1 (23 already-warm fake apps, emptyDir state):

```json
{
  "pods": 23,
  "ready": 23,
  "ready_ratio": 1.0,
  "ready_latency_sec": {
    "count": 23,
    "min": 11.0,
    "p50": 255.0,
    "p95": 7736.0,
    "max": 9391.0
  },
  "persistent_volume_claims": {
    "claims": 0,
    "pending": 0
  },
  "fast_provisioning_ready": true
}
```

Slot 4 (2 Tier 4 apps using operator DBs):

```json
{
  "pods": 2,
  "ready": 2,
  "ready_ratio": 1.0,
  "ready_latency_sec": {
    "count": 2,
    "min": 11.0,
    "p50": 34.0,
    "p95": 57.0,
    "max": 57.0
  },
  "persistent_volume_claims": {
    "claims": 2,
    "bound": 2,
    "pending": 0
  },
  "fast_provisioning_ready": true
}
```

## Interpretation

The fast path is not "create a new namespace from scratch every time." The
current evidence favors:

1. Prewarmed slot or app pool as the primary latency reducer.
2. Operator-managed DB reuse for DB-backed apps.
3. PVC snapshot/restore only where file-backed state needs isolation.
4. Provisioning metrics in CI/release validation to catch regressions.

Slot 1's long p95/max reflects cold app starts accumulated in the same slot.
Slot 4's operator-backed subset shows much lower observed ready latency because
the DB layer and images were already warm.

## Next Safe Steps

- Run the same measurement before and after any prewarmed-pool change.
- Add per-app metrics so slow apps are identified explicitly.
- Track snapshot restore latency separately from image pull and DB startup.
- Keep cluster validation read-only or restricted to a dedicated slot.
