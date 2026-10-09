"""Auto-loaded shim that redirects Docker CLI calls to Kubernetes."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys


_SHIM_DIR = os.path.dirname(os.path.abspath(__file__))
_SHIM_PATH = os.path.join(_SHIM_DIR, "docker_shim.py")

_spec = importlib.util.spec_from_file_location("saas_k8s_docker_shim", _SHIM_PATH)
_shim = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_shim)

_original_run = subprocess.run
_original_check_output = subprocess.check_output
_original_check_call = subprocess.check_call


def _is_docker(args):
    return isinstance(args, (list, tuple)) and bool(args) and str(args[0]).lower() == "docker"


def _rewrite(args):
    return [sys.executable, _SHIM_PATH, *list(args)[1:]]


def _run(*args, **kwargs):
    cmd = args[0] if args else kwargs.get("args")
    if _is_docker(cmd):
        new_args = (_rewrite(cmd), *args[1:])
        return _original_run(*new_args, **kwargs)
    return _original_run(*args, **kwargs)


def _check_output(*args, **kwargs):
    cmd = args[0] if args else kwargs.get("args")
    if _is_docker(cmd):
        new_args = (_rewrite(cmd), *args[1:])
        return _original_check_output(*new_args, **kwargs)
    return _original_check_output(*args, **kwargs)


def _check_call(*args, **kwargs):
    cmd = args[0] if args else kwargs.get("args")
    if _is_docker(cmd):
        new_args = (_rewrite(cmd), *args[1:])
        return _original_check_call(*new_args, **kwargs)
    return _original_check_call(*args, **kwargs)


subprocess.run = _run
subprocess.check_output = _check_output
subprocess.check_call = _check_call


def _install_gateway_requests_shim() -> None:
    import json
    import urllib.parse

    try:
        import requests
    except Exception:
        return

    raw = os.environ.get("SAAS_GATEWAY_PORTS", "")
    if not raw:
        return
    try:
        port_hosts = json.loads(raw)
    except json.JSONDecodeError:
        return
    if not port_hosts:
        return

    original_request = requests.Session.request

    def request(self, method, url, *args, **kwargs):
        parsed = urllib.parse.urlsplit(str(url))
        if parsed.scheme in {"http", "https"} and parsed.port is not None:
            host = port_hosts.get(str(parsed.port))
            if host:
                url = urllib.parse.urlunsplit((parsed.scheme, host, parsed.path, parsed.query, parsed.fragment))
        return original_request(self, method, url, *args, **kwargs)

    requests.Session.request = request


_install_gateway_requests_shim()
