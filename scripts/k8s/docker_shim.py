#!/usr/bin/env python3
"""Compatibility shim that maps Docker verification commands to kubectl."""

from __future__ import annotations

import json
import os
import subprocess
import sys


def kubectl(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["kubectl", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def load_map() -> dict:
    raw = os.environ.get("SAAS_K8S_EXEC_MAP", "{}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def resolve(target: str) -> dict | None:
    return load_map().get(target)


def find_pod(namespace: str, selector: str) -> str:
    result = kubectl([
        "-n", namespace,
        "get", "pods",
        "-l", selector,
        "-o", "jsonpath={.items[0].metadata.name}",
    ])
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(result.stderr or f"no pod found for selector {selector}")
    return result.stdout.strip()


def parse_exec(args: list[str]) -> tuple[list[str], str, list[str]]:
    envs: list[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--":
            i += 1
            break
        if arg in ("-e", "--env"):
            envs.append(args[i + 1])
            i += 2
            continue
        if arg.startswith("--env="):
            envs.append(arg.split("=", 1)[1])
            i += 1
            continue
        if arg in ("-i", "-t", "-it", "-ti", "--interactive", "--tty"):
            i += 1
            continue
        if arg in ("-u", "--user", "-w", "--workdir"):
            i += 2
            continue
        if arg.startswith("-"):
            i += 1
            continue
        break
    if i >= len(args):
        raise RuntimeError("docker exec requires a target container")
    return envs, args[i], args[i + 1:]


def docker_exec(args: list[str]) -> int:
    envs, target, command = parse_exec(args)
    info = resolve(target)
    if not info:
        raise RuntimeError(f"no Kubernetes mapping for container {target!r}")
    pod = find_pod(info["namespace"], info["selector"])
    cmd = ["kubectl", "-n", info["namespace"], "exec", pod, "-c", info["container"], "--"]
    if envs:
        cmd += ["env", *envs]
    cmd += command
    result = subprocess.run(cmd, text=True, encoding="utf-8", errors="replace")
    return result.returncode


def parse_cp_endpoint(value: str) -> tuple[str, str] | None:
    # Windows local paths (C:\..., D:/...) contain ':', but are not container endpoints.
    if len(value) >= 2 and value[1] == ":" and value[0].isalpha():
        return None
    if ":" not in value:
        return None
    container, path = value.split(":", 1)
    return container, path


def mapped_cp_endpoint(value: str) -> tuple[str, str | None]:
    endpoint = parse_cp_endpoint(value)
    if not endpoint:
        return value, None
    target, path = endpoint
    info = resolve(target)
    if not info:
        raise RuntimeError(f"no Kubernetes mapping for container {target!r}")
    pod = find_pod(info["namespace"], info["selector"])
    return f"{pod}:{path}", info["container"]


def _container_endpoint(value: str) -> tuple[dict, str] | None:
    endpoint = parse_cp_endpoint(value)
    if not endpoint:
        return None
    target, path = endpoint
    info = resolve(target)
    if not info:
        raise RuntimeError(f"no Kubernetes mapping for container {target!r}")
    return info, path


def _copy_from_container(info: dict, path: str, local_path: str) -> int:
    pod = find_pod(info["namespace"], info["selector"])
    result = subprocess.run(
        ["kubectl", "-n", info["namespace"], "exec", pod, "-c", info["container"], "--", "cat", path],
        capture_output=True,
    )
    if result.returncode != 0:
        sys.stderr.buffer.write(result.stderr)
        return result.returncode
    with open(local_path, "wb") as handle:
        handle.write(result.stdout)
    return 0


def _copy_to_container(local_path: str, info: dict, path: str) -> int:
    pod = find_pod(info["namespace"], info["selector"])
    with open(local_path, "rb") as handle:
        data = handle.read()
    result = subprocess.run(
        ["kubectl", "-n", info["namespace"], "exec", "-i", pod, "-c", info["container"], "--", "sh", "-c", f"cat > {path}"],
        input=data,
        capture_output=True,
    )
    if result.returncode != 0:
        sys.stderr.buffer.write(result.stderr)
        return result.returncode
    return 0


def docker_cp(args: list[str]) -> int:
    if len(args) < 2:
        raise RuntimeError("docker cp requires source and destination")
    operands = [arg for arg in args if not arg.startswith("-")]
    if len(operands) < 2:
        raise RuntimeError("docker cp requires source and destination operands")
    src = operands[-2]
    dst = operands[-1]
    src_endpoint = _container_endpoint(src)
    dst_endpoint = _container_endpoint(dst)
    if src_endpoint and not dst_endpoint:
        return _copy_from_container(src_endpoint[0], src_endpoint[1], dst)
    if dst_endpoint and not src_endpoint:
        return _copy_to_container(src, dst_endpoint[0], dst_endpoint[1])
    src_mapped, src_container = mapped_cp_endpoint(src)
    dst_mapped, dst_container = mapped_cp_endpoint(dst)
    cmd = ["kubectl", "cp", src_mapped, dst_mapped]
    if src_container:
        cmd += ["-c", src_container]
    elif dst_container:
        cmd += ["-c", dst_container]
    result = subprocess.run(cmd, text=True, encoding="utf-8", errors="replace")
    return result.returncode


def docker_logs(args: list[str]) -> int:
    target = next((a for a in args if not a.startswith("-")), None)
    if not target:
        raise RuntimeError("docker logs requires a container")
    info = resolve(target)
    if not info:
        raise RuntimeError(f"no Kubernetes mapping for container {target!r}")
    pod = find_pod(info["namespace"], info["selector"])
    result = subprocess.run(
        ["kubectl", "-n", info["namespace"], "logs", pod, "-c", info["container"]],
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode


def main() -> int:
    if len(sys.argv) < 2:
        print("docker shim: missing command", file=sys.stderr)
        return 2
    command = sys.argv[1]
    rest = sys.argv[2:]
    try:
        if command == "exec":
            return docker_exec(rest)
        if command == "cp":
            return docker_cp(rest)
        if command == "logs":
            return docker_logs(rest)
        if command == "ps":
            return kubectl(["get", "pods", "-A"]).returncode
        if command == "inspect":
            print("{}")
            return 0
        print(f"docker shim: unsupported docker command {command!r}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"docker shim: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
