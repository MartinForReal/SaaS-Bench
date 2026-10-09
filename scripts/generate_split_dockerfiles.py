"""Generate one Dockerfile per service from the multi-service SaaS-Bench images.

The upstream mw-* images bundle the app plus its database, cache and web server in a
single container (supervisord / a wrapper entrypoint). Each generated Dockerfile
derives from the same base image but runs exactly one service, so a pod can place
them in separate containers (or separate pods).
"""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docker" / "split"

# image -> {service: (binary/entrypoint, args)}
SPLITS: dict[str, dict[str, tuple[str, list[str]]]] = {
    "mw-baserow": {
        "db": ("postgres", ["-D", "/baserow/data/postgres"]),
        "redis": ("redis-server", ["--bind", "127.0.0.1", "--port", "6379"]),
        "app": ("/baserow.sh", ["backend-cmd", "run"]),
    },
    "mw-bigcapital": {
        "db": ("mysqld_safe", ["--user=mysql"]),
        "redis": ("redis-server", ["--port", "6379"]),
        "nginx": ("nginx", ["-g", "daemon off;"]),
        "server": ("/usr/local/bin/node", ["build/main.js"]),
    },
    "mw-booklore": {
        "db": ("mariadbd", ["--user=mysql", "--datadir=/var/lib/mysql"]),
        "app": ("/__cacert_entrypoint.sh", ["/start.sh"]),
    },
    "mw-hrms": {
        "db": ("mariadbd", ["--user=mysql", "--datadir=/var/lib/mysql"]),
        "redis": ("redis-server", ["--port", "6379"]),
        "app": ("/mw-entrypoint.sh", []),
    },
    "mw-openemr": {
        "db": ("mariadbd", ["--user=mysql", "--datadir=/var/lib/mysql"]),
        "app": ("/openemr.sh", []),
    },
    "mw-openproject": {
        "db": ("/usr/lib/postgresql/17/bin/postgres", ["-D", "/var/openproject/pgdata"]),
        "app": ("/entrypoint-wrapper.sh", ["./docker/prod/supervisord"]),
    },
    "mw-opnform": {
        "db": ("postgres", ["-D", "/var/lib/postgresql/data"]),
        "redis": ("redis-server", ["--port", "6379"]),
        "nginx": ("nginx", ["-g", "daemon off;"]),
        "app": ("php-fpm", ["-F"]),
        "worker": ("php", ["artisan", "queue:work"]),
    },
    "mw-photoprism": {
        "db": ("mariadbd", ["--user=mysql", "--datadir=/var/lib/mysql"]),
        "app": ("/photoprism", ["start"]),
    },
    "mw-pretix": {
        "db": ("postgres", ["-D", "/var/lib/postgresql/data"]),
        "redis": ("redis-server", ["--port", "6379"]),
        "nginx": ("nginx", ["-g", "daemon off;"]),
        "web": ("/entrypoint-mw.sh", ["web"]),
        "task": ("/entrypoint-mw.sh", ["task"]),
    },
    "mw-roundcubemail": {
        "db": ("mariadbd", ["--user=mysql", "--datadir=/var/lib/mysql"]),
        "web": ("apache2ctl", ["-D", "FOREGROUND"]),
        "mta": ("/usr/lib/postfix/sbin/master", ["-d"]),
        "imap": ("dovecot", ["-F"]),
    },
    "mw-twenty": {
        "db": ("postgres", ["-D", "/var/lib/postgresql/data"]),
        "redis": ("redis-server", ["--port", "6379"]),
        "app": ("node", ["dist/main"]),
    },
    "oo-bundle-community2": {
        "db": ("mysqld", ["--user=mysql"]),
        "redis": ("redis-server", ["--port", "6379"]),
        "nginx": ("nginx", ["-g", "daemon off;"]),
        "app": ("monoserve", []),
    },
    "oo-bundle-ds": {
        "docservice": ("/usr/bin/documentserver-example", []),
        "converter": ("/usr/bin/documentserver-converter", []),
    },
}

TEMPLATE = """# syntax=docker/dockerfile:1.7
#
# Split image: ONE service per container.
#
# Source bundle : {image}
# Service      : {service}
# Runs         : {binary} {args}
#
# The base image already ships the binaries, config and fixtures; this image only
# pins the entrypoint to a single service so the database / cache / web server can
# run as their own container instead of being launched by supervisord.
#
# Runtime expectations:
#   * the data directory must be a volume or emptyDir mounted at the path the
#     service uses by default;
#   * peer services are reached over the network via env vars (DB_HOST, REDIS_HOST,
#     ...) that the app service must be given instead of its bundled defaults.

ARG BASE_IMAGE={image}:latest
FROM ${{BASE_IMAGE}}

USER root
ENTRYPOINT []
CMD [{cmd}]
"""


def render(image: str, service: str, spec: tuple[str, list[str]]) -> str:
    binary, args = spec
    cmd = ", ".join([f'"{binary}"'] + [f'"{a}"' for a in args])
    return TEMPLATE.format(
        image=image,
        service=service,
        binary=binary,
        args=" ".join(args),
        cmd=cmd,
    )


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    written = 0
    for image, services in SPLITS.items():
        for service, spec in services.items():
            path = OUT / image / f"Dockerfile.{service}"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render(image, service, spec), encoding="utf-8")
            written += 1
    print(f"wrote {written} Dockerfiles under {OUT}")


if __name__ == "__main__":
    main()