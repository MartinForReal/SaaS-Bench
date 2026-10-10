from datetime import UTC, datetime, timedelta

from saas_bench.provisioning_metrics import (
    ProvisioningSnapshot,
    pod_ready_latency_sec,
    summarize,
    summarize_persistent_volume_claims,
    summarize_pods,
)


def _pod(*, ready: bool, created: datetime, ready_at: datetime | None = None) -> dict:
    conditions = []
    if ready_at is not None:
        conditions.append(
            {"type": "Ready", "status": "True" if ready else "False", "lastTransitionTime": ready_at.isoformat()}
        )
    return {
        "metadata": {"creationTimestamp": created.isoformat()},
        "status": {
            "phase": "Running",
            "conditions": conditions,
            "containerStatuses": [{"ready": ready}],
        },
    }


def test_summarize_reports_percentiles() -> None:
    assert summarize([10, 20, 30, 40]) == {"count": 4, "min": 10.0, "p50": 25.0, "p95": 40.0, "max": 40.0}


def test_pod_ready_latency_uses_ready_transition() -> None:
    created = datetime(2026, 1, 1, tzinfo=UTC)
    pod = _pod(ready=True, created=created, ready_at=created + timedelta(seconds=12.5))
    assert pod_ready_latency_sec(pod) == 12.5


def test_summarize_pods_counts_ready_and_latency() -> None:
    created = datetime(2026, 1, 1, tzinfo=UTC)
    pods = [
        _pod(ready=True, created=created, ready_at=created + timedelta(seconds=5)),
        _pod(ready=False, created=created, ready_at=None),
    ]
    summary = summarize_pods(pods)
    assert summary["pods"] == 2
    assert summary["ready"] == 1
    assert summary["ready_ratio"] == 0.5
    assert summary["ready_latency_sec"]["count"] == 1


def test_pvc_summary_requires_no_pending() -> None:
    assert summarize_persistent_volume_claims(
        [{"status": {"phase": "Bound"}}, {"status": {"phase": "Pending"}}]
    ) == {"claims": 2, "bound": 1, "pending": 1, "bound_ratio": 0.5}


def test_snapshot_marks_fast_provisioning_ready() -> None:
    snapshot = ProvisioningSnapshot(
        namespace="saas-bench-slot-4",
        pods={"pods": 2, "ready": 2},
        persistent_volume_claims={"claims": 1, "bound": 1, "pending": 0, "bound_ratio": 1.0},
    )
    assert snapshot.as_dict()["fast_provisioning_ready"] is True
