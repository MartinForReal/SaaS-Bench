#!/usr/bin/env python3
"""Measure SaaS-Bench provisioning readiness without mutating a slot."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from saas_bench.provisioning_metrics import (  # noqa: E402
    ProvisioningSnapshot,
    summarize_persistent_volume_claims,
    summarize_pods,
)


def _kubectl_json(kubeconfig: str, *args: str) -> dict:
    command = ["kubectl", *args, "-o", "json"]
    if kubeconfig:
        command.extend(["--kubeconfig", kubeconfig])
    proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"kubectl failed: {' '.join(command)}")
    return json.loads(proc.stdout)


def measure(kubeconfig: str, namespace: str) -> dict:
    pods = _kubectl_json(
        kubeconfig,
        "-n",
        namespace,
        "get",
        "pods",
        "-l",
        "app.kubernetes.io/component=saas-bench-app",
    )
    claims = _kubectl_json(kubeconfig, "-n", namespace, "get", "persistentvolumeclaims")
    snapshot = ProvisioningSnapshot(
        namespace=namespace,
        pods=summarize_pods(list(pods.get("items") or [])),
        persistent_volume_claims=summarize_persistent_volume_claims(list(claims.get("items") or [])),
    )
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        **snapshot.as_dict(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kubeconfig", default="")
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args()
    result = measure(args.kubeconfig, args.namespace)
    out = Path(args.result)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["fast_provisioning_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
