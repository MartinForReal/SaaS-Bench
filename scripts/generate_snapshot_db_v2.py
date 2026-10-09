"""Snapshot DB images v2: staging datadir + explicit socket + loud readiness wait."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docker" / "split"

MARIA = r"""# syntax=docker/dockerfile:1.7
ARG BASE_IMAGE=__BASE__:latest
FROM ${BASE_IMAGE} AS snapshot
USER root
RUN set -eux; \
    mkdir -p /opt/snapshot/mysql /run/mysqld; \
    chown -R mysql:mysql /opt/snapshot/mysql /run/mysqld; \
    mariadb-install-db --user=mysql --datadir=/opt/snapshot/mysql >/dev/null; \
    mysqld_safe --user=mysql --datadir=/opt/snapshot/mysql --socket=/run/mysqld/snap.sock --skip-networking & \
    ok=0; \
    for i in $(seq 1 120); do \
      if mariadb-admin --socket=/run/mysqld/snap.sock ping >/dev/null 2>&1; then ok=1; break; fi; \
      sleep 1; \
    done; \
    [ "$ok" = "1" ] || { echo "FATAL: mariadb socket never came up"; exit 1; }; \
__SEED__     mariadb --socket=/run/mysqld/snap.sock -e "CREATE USER IF NOT EXISTS 'root'@'127.0.0.1' IDENTIFIED BY ''; GRANT ALL PRIVILEGES ON *.* TO 'root'@'127.0.0.1' WITH GRANT OPTION; FLUSH PRIVILEGES;" && \
    mariadb-admin --socket=/run/mysqld/snap.sock shutdown; \
    rm -f /opt/snapshot/mysql/*.pid /opt/snapshot/mysql/*.err /run/mysqld/snap.sock
COPY entrypoint-db.sh /opt/saas-bench/entrypoint-db.sh
RUN chmod +x /opt/saas-bench/entrypoint-db.sh

FROM scratch AS runtime
COPY --from=snapshot / /
ENTRYPOINT ["/opt/saas-bench/entrypoint-db.sh"]
"""

PG = r"""# syntax=docker/dockerfile:1.7
ARG BASE_IMAGE=__BASE__:latest
FROM ${BASE_IMAGE} AS snapshot
USER root
RUN set -eux; \
    mkdir -p /opt/snapshot/pgdata /run/postgresql; \
    chown -R postgres:postgres /opt/snapshot/pgdata /run/postgresql; \
    su postgres -s /bin/bash -c "initdb -D /opt/snapshot/pgdata"; \
    echo "host all all 127.0.0.1/32 trust" >> /opt/snapshot/pgdata/pg_hba.conf; \
    echo "listen_addresses = 127.0.0.1" >> /opt/snapshot/pgdata/postgresql.conf; \
    su postgres -s /bin/bash -c "pg_ctl -D /opt/snapshot/pgdata -o '-k /run/postgresql -p 5433' -l /tmp/snap.log -w start"; \
    ok=0; \
    for i in $(seq 1 60); do \
      if su postgres -s /bin/bash -c "pg_isready -h 127.0.0.1 -p 5433" >/dev/null 2>&1; then ok=1; break; fi; \
      sleep 1; \
    done; \
    [ "$ok" = "1" ] || { echo "FATAL: postgres never became ready"; cat /tmp/snap.log || true; exit 1; }; \
__SEED__     su postgres -s /bin/bash -c "pg_ctl -D /opt/snapshot/pgdata -m fast -w stop"; \
    rm -f /opt/snapshot/pgdata/postmaster.pid
COPY entrypoint-db.sh /opt/saas-bench/entrypoint-db.sh
RUN chmod +x /opt/saas-bench/entrypoint-db.sh

FROM scratch AS runtime
COPY --from=snapshot / /
ENTRYPOINT ["/opt/saas-bench/entrypoint-db.sh"]
"""

HRMS_SEED = r"""    mariadb --socket=/run/mysqld/snap.sock -e "CREATE DATABASE IF NOT EXISTS \`_041806a949bb7dd0\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" && \
    mariadb --socket=/run/mysqld/snap.sock _041806a949bb7dd0 < /mw-hrms-dump.sql && \
    mariadb --socket=/run/mysqld/snap.sock -e "CREATE USER IF NOT EXISTS '_041806a949bb7dd0'@'%' IDENTIFIED BY '1yMa70SeWYjkbmK9'; GRANT ALL PRIVILEGES ON \`_041806a949bb7dd0\`.* TO '_041806a949bb7dd0'@'%'; FLUSH PRIVILEGES;" && \
"""

PG_SEED_COMMON = r"""    su postgres -s /bin/bash -c "psql -p 5433 -c \"CREATE USER {u} WITH PASSWORD '{p}' SUPERUSER;\"" && \
    su postgres -s /bin/bash -c "psql -p 5433 -c \"CREATE DATABASE {d} OWNER {u};\"" && \
"""

PRETIX_SEED = PG_SEED_COMMON.format(u="pretix", p="pretix", d="pretix") + r"""    (cd /pretix/src && DJANGO_SETTINGS_MODULE=production_settings DATA_DIR=/data/ HOME=/pretix python3 -m pretix migrate --noinput) || true && \
"""
TWENTY_SEED = PG_SEED_COMMON.format(u="postgres", p="twenty_postgres_pass", d="default") + r"""    PG_DATABASE_URL="postgres://postgres:twenty_postgres_pass@127.0.0.1:5433/default" DISABLE_CRON_JOBS_REGISTRATION=true /app/entrypoint.sh true && \
"""
OPNFORM_SEED = PG_SEED_COMMON.format(u="forge", p="forge", d="forge") + r"""    su postgres -s /bin/bash -c "pg_restore -p 5433 -U forge -d forge --no-owner --no-privileges /docker-entrypoint-initdb.d/opnform_dump.dump" || true && \
"""

FILES = {
    "mw-hrms/Dockerfile.db": MARIA.replace("__BASE__", "mw-hrms").replace("__SEED__", HRMS_SEED),
    "mw-booklore/Dockerfile.db": MARIA.replace("__BASE__", "mw-booklore").replace("__SEED__", ""),
    "mw-pretix/Dockerfile.db": PG.replace("__BASE__", "mw-pretix").replace("__SEED__", PRETIX_SEED),
    "mw-twenty/Dockerfile.db": PG.replace("__BASE__", "mw-twenty").replace("__SEED__", TWENTY_SEED),
    "mw-opnform/Dockerfile.db": PG.replace("__BASE__", "mw-opnform").replace("__SEED__", OPNFORM_SEED),
}

SERVE = {
    "mw-hrms": "#!/bin/sh\nset -e\nmkdir -p /var/lib/mysql\n[ -d /var/lib/mysql/mysql ] || cp -a /opt/snapshot/mysql/. /var/lib/mysql/\nexec mariadbd --user=mysql --datadir=/var/lib/mysql --bind-address=0.0.0.0 --port=3306 --skip-networking=0\n",
    "mw-booklore": "#!/bin/sh\nset -e\nmkdir -p /var/lib/mysql\n[ -d /var/lib/mysql/mysql ] || cp -a /opt/snapshot/mysql/. /var/lib/mysql/\nexec mariadbd --user=mysql --datadir=/var/lib/mysql --bind-address=0.0.0.0 --port=3306 --skip-networking=0\n",
    "mw-pretix": "#!/bin/sh\nset -e\nmkdir -p /var/lib/postgresql/data /run/postgresql\nchown -R postgres:postgres /var/lib/postgresql/data /run/postgresql\n[ -f /var/lib/postgresql/data/PG_VERSION ] || cp -a /opt/snapshot/pgdata/. /var/lib/postgresql/data/\nexec su postgres -s /bin/bash -c \"postgres -D /var/lib/postgresql/data -k /run/postgresql\"\n",
    "mw-twenty": "#!/bin/sh\nset -e\nmkdir -p /var/lib/postgresql/data /run/postgresql\nchown -R postgres:postgres /var/lib/postgresql/data /run/postgresql\n[ -f /var/lib/postgresql/data/PG_VERSION ] || cp -a /opt/snapshot/pgdata/. /var/lib/postgresql/data/\nexec su-exec postgres postgres -D /var/lib/postgresql/data -k /run/postgresql\n",
    "mw-opnform": "#!/bin/sh\nset -e\nmkdir -p /var/lib/postgresql/data /run/postgresql\nchown -R postgres:postgres /var/lib/postgresql/data /run/postgresql\n[ -f /var/lib/postgresql/data/PG_VERSION ] || cp -a /opt/snapshot/pgdata/. /var/lib/postgresql/data/\nPG_BIN=/usr/libexec/postgresql16; [ -d \"$PG_BIN\" ] || PG_BIN=/usr/bin\nexec su - postgres -s /bin/bash -c \"$PG_BIN/postgres -D /var/lib/postgresql/data -k /run/postgresql\"\n",
}

for rel, content in FILES.items():
    (OUT / rel).write_text(content, encoding="utf-8", newline="\n")
for image, script in SERVE.items():
    (OUT / image / "entrypoint-db.sh").write_text(script, encoding="utf-8", newline="\n")
print("snapshot v2 written:", len(FILES), "dockerfiles,", len(SERVE), "entrypoints")