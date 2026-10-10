#!/usr/bin/env python3
"""Evaluate SaaS-Bench slot reset deterministically and record latency evidence.

This evaluator is intentionally independent of the SaaS-Bench verifier. It tests
the slot-manager contract itself:

  status -> reset -> status -> public probe

The evaluator supports self-signed TLS by default, repeated trials, aggregate
latency statistics, and stable exit codes.
"""
from __future__ import annotations

import argparse
import json
import statistics
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_ERROR = 2
UNVERIFIED_CONTEXT = ssl._create_unverified_context()


def _request(
    url: str,
    method: str = "GET",
    timeout: int = 30,
    *,
    context: ssl.SSLContext | None = None,
) -> tuple[int, str]:
    req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def _status_is_ready(body: str) -> bool:
    try:
        return json.loads(body).get("status") == "ready"
    except json.JSONDecodeError:
        return False


def _latency_stats(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"count": 0}
    ordered = sorted(values)
    p95_index = min(len(ordered) - 1, max(0, int(round(0.95 * (len(ordered) - 1)))))
    return {
        "count": len(values),
        "min_sec": round(min(values), 3),
        "mean_sec": round(statistics.fmean(values), 3),
        "median_sec": round(statistics.median(values), 3),
        "p95_sec": round(ordered[p95_index], 3),
        "max_sec": round(max(values), 3),
    }


def _run_trial(
    *,
    trial: int,
    controller: str,
    slot: int,
    app: str,
    public_url: str,
    timeout_sec: int,
    skip_reset: bool,
    context: ssl.SSLContext | None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "trial": trial,
        "before": None,
        "reset": None,
        "after": None,
        "public_probe": None,
        "elapsed_sec": None,
        "status": "ERROR",
    }
    started = time.monotonic()
    try:
        code, body = _request(f"{controller}/slots/{slot}/status", timeout=30, context=context)
        result["before"] = {"http": code, "body": body}
        if not skip_reset:
            reset_url = (
                f"{controller}/slots/{slot}/reset"
                f"?apps={app}&wait=true&timeout_sec={timeout_sec}"
            )
            code, body = _request(
                reset_url,
                method="POST",
                timeout=timeout_sec + 60,
                context=context,
            )
            result["reset"] = {"http": code, "body": body}
        code, body = _request(f"{controller}/slots/{slot}/status", timeout=30, context=context)
        result["after"] = {"http": code, "body": body}
        code, body = _request(public_url, timeout=30, context=context)
        result["public_probe"] = {"http": code, "body_prefix": body[:500]}
        reset_ok = result["reset"] is None or result["reset"]["http"] == 200
        after_ready = _status_is_ready((result["after"] or {}).get("body", ""))
        public_ok = 200 <= code < 400
        result["status"] = "PASS" if reset_ok and after_ready and public_ok else "FAIL"
    except Exception as exc:  # noqa: BLE001 - evidence must retain any transport failure
        result["error"] = f"{type(exc).__name__}: {exc}"
    result["elapsed_sec"] = round(time.monotonic() - started, 3)
    return result


def evaluate(
    *,
    controller: str,
    slot: int,
    app: str,
    public_url: str,
    timeout_sec: int = 900,
    skip_reset: bool = False,
    trials: int = 1,
    verify_tls: bool = False,
    result_path: str | Path | None = None,
) -> tuple[int, dict[str, Any]]:
    if trials < 1:
        raise ValueError("trials must be >= 1")
    context = None if verify_tls else UNVERIFIED_CONTEXT
    trial_results = [
        _run_trial(
            trial=index,
            controller=controller,
            slot=slot,
            app=app,
            public_url=public_url,
            timeout_sec=timeout_sec,
            skip_reset=skip_reset,
            context=context,
        )
        for index in range(trials)
    ]
    latency_values = [float(item["elapsed_sec"]) for item in trial_results if item["elapsed_sec"] is not None]
    statuses = [item["status"] for item in trial_results]
    if all(status == "PASS" for status in statuses):
        overall = "PASS"
        exit_code = EXIT_PASS
    elif any(status == "FAIL" for status in statuses):
        overall = "FAIL"
        exit_code = EXIT_FAIL
    else:
        overall = "ERROR"
        exit_code = EXIT_ERROR
    payload = {
        "slot": slot,
        "app": app,
        "controller": controller,
        "public_url": public_url,
        "skip_reset": skip_reset,
        "verify_tls": verify_tls,
        "trials_requested": trials,
        "trials": trial_results,
        "latency": _latency_stats(latency_values),
        "status": overall,
    }
    if result_path is not None:
        out = Path(result_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return exit_code, payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--controller", default="http://127.0.0.1:8080")
    parser.add_argument("--slot", type=int, required=True)
    parser.add_argument("--app", required=True)
    parser.add_argument("--public-url", required=True)
    parser.add_argument("--timeout-sec", type=int, default=900)
    parser.add_argument("--result", required=True)
    parser.add_argument("--skip-reset", action="store_true")
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument(
        "--verify-tls",
        action="store_true",
        help="Verify public TLS certificates. Default is insecure for the self-signed test cert.",
    )
    args = parser.parse_args()
    exit_code, payload = evaluate(
        controller=args.controller,
        slot=args.slot,
        app=args.app,
        public_url=args.public_url,
        timeout_sec=args.timeout_sec,
        skip_reset=args.skip_reset,
        trials=args.trials,
        verify_tls=args.verify_tls,
        result_path=args.result,
    )
    print(json.dumps(payload, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
