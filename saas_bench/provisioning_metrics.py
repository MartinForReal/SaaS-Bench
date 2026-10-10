"""Fast-provisioning metrics for SaaS-Bench slots.

Pure helpers live here so the measurement CLI can stay a thin kubectl wrapper and
the latency math is unit-testable without a cluster.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import median
from typing import Any, Iterable


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def summarize(values: Iterable[float]) -> dict[str, float | int | None]:
    samples = [float(value) for value in values]
    if not samples:
        return {"count": 0, "min": None, "p50": None, "p95": None, "max": None}
    return {
        "count": len(samples),
        "min": round(min(samples), 3),
        "p50": round(float(median(samples)), 3),
        "p95": round(float(percentile(samples, 0.95) or 0.0), 3),
        "max": round(max(samples), 3),
    }


def pod_ready_latency_sec(pod: dict[str, Any]) -> float | None:
    metadata = pod.get("metadata") or {}
    status = pod.get("status") or {}
    created = parse_timestamp(metadata.get("creationTimestamp"))
    ready = None
    for condition in status.get("conditions") or []:
        if condition.get("type") == "Ready" and condition.get("status") == "True":
            ready = parse_timestamp(condition.get("lastTransitionTime"))
            break
    if created is None or ready is None:
        return None
    return max(0.0, (ready - created).total_seconds())


def summarize_pods(pods: list[dict[str, Any]]) -> dict[str, Any]:
    ready_count = 0
    latencies: list[float] = []
    for pod in pods:
        status = pod.get("status") or {}
        if status.get("phase") == "Running" and all(
            container.get("ready") for container in status.get("containerStatuses") or []
        ):
            ready_count += 1
        latency = pod_ready_latency_sec(pod)
        if latency is not None:
            latencies.append(latency)
    return {
        "pods": len(pods),
        "ready": ready_count,
        "ready_ratio": round(ready_count / len(pods), 3) if pods else 0.0,
        "ready_latency_sec": summarize(latencies),
    }


def summarize_persistent_volume_claims(claims: list[dict[str, Any]]) -> dict[str, Any]:
    bound = 0
    pending = 0
    for claim in claims:
        phase = (claim.get("status") or {}).get("phase")
        if phase == "Bound":
            bound += 1
        elif phase == "Pending":
            pending += 1
    return {
        "claims": len(claims),
        "bound": bound,
        "pending": pending,
        "bound_ratio": round(bound / len(claims), 3) if claims else 1.0,
    }


@dataclass(frozen=True)
class ProvisioningSnapshot:
    namespace: str
    pods: dict[str, Any]
    persistent_volume_claims: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "pods": self.pods,
            "persistent_volume_claims": self.persistent_volume_claims,
            "fast_provisioning_ready": (
                self.pods["pods"] > 0
                and self.pods["ready"] == self.pods["pods"]
                and self.persistent_volume_claims["pending"] == 0
            ),
        }
