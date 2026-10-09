# Slot Snapshot and PVC Reset Design

Status: active implementation
Owner: Codex
Tracker: DSH goal-604f2e70-b67e-4ea4-8855-117a8bdd7c0f

## Goal

Make SaaS-Bench slots reproducible from immutable snapshots. A slot reset must return
the app to a clean boot state without rerunning slow database imports, migrations,
asset builds, or project setup inside every pod.

## Core Design

1. Build immutable snapshots once per app/image version.
2. Store each snapshot as a versioned artifact:
   - DB datadir snapshot stored in an image layer, blob archive, or CSI VolumeSnapshot.
   - Project files and compiled assets stored the same way.
3. Provision each slot from the snapshot:
   - Default mode: copy or untar the snapshot into an emptyDir at pod start.
   - Durable PVC mode: create a PVC from a VolumeSnapshot before starting the pod.
4. Reset:
   - Delete the slot pod/PVC.
   - Recreate from the same immutable snapshot.
   - The app starts in the clean snapshot state.

## Snapshot Artifact Model

```yaml
apiVersion: saas-bench.io/v1alpha1
kind: SlotSnapshot
metadata:
  name: watcharr-20261010
spec:
  app: watcharr
  imageTag: 20261010-953b1ecbea0e
  db:
    kind: image | blob | volumeSnapshot
    ref: <image-digest | blob-uri | snapshot-name>
  project:
    kind: image | blob | volumeSnapshot
    ref: <image-digest | blob-uri | snapshot-name>
  readyMarker: /opt/snapshot/READY
```

## Runtime Layout

The snapshot must be staged outside the runtime data path:

```text
/opt/snapshot/pgdata
/opt/snapshot/mysql
/opt/snapshot/project
/opt/snapshot/READY
```

The pod's data path is backed by emptyDir or PVC:

```text
/var/lib/postgresql/data
/var/lib/mysql
/home/coder/workspace
```

If an emptyDir or PVC is mounted over the runtime data path, the baked snapshot is
hidden. Entrypoints must copy from /opt/snapshot/* into the runtime path on first
start.

## DB Snapshot Rules

- Snapshot only after a clean stop, or use a hot-copy tool:
  - PostgreSQL: pg_basebackup or pg_ctl -m fast -w stop
  - MariaDB/MySQL: mariabackup --prepare or mariadb-admin shutdown
- Remove pid files before packaging.
- Fail the build if the DB never becomes ready.
- Use explicit sockets during build:
  - PostgreSQL: -k /run/postgresql -p 5433
  - MariaDB: --socket=/run/mysqld/snap.sock

## One Service Per Container

Every multi-service image must become one-service-per-container Dockerfiles:

- db
- redis
- app
- worker
- scheduler
- nginx / web server
- task worker

Each Dockerfile must use a real service-specific entrypoint. A CMD override alone is
not sufficient because bundled entrypoints often run migrations, seed fixtures, or
start all services.

Bundled image candidates already identified:

| Image | Services |
|---|---|
| mw-baserow | postgres, redis, baserow |
| mw-bigcapital | gotenberg, mysql, nginx, redis, server |
| mw-booklore | mariadb, app |
| mw-hrms | mariadb, redis, frappe |
| mw-openemr | mariadb, openemr |
| mw-openproject | postgres, app |
| mw-opnform | postgres, redis, nginx, php-fpm, queue-worker, scheduler, client |
| mw-photoprism | mariadb, app |
| mw-pretix | nginx, postgres, pretixweb, pretixtask, redis |
| mw-roundcubemail | apache, mariadb, postfix, dovecot, clamav, rspamd, amavis, fail2ban, cron |
| mw-twenty | postgres, redis, node app |
| oo-bundle-community2 | nginx, mysqld, redis, monoserve, workers |
| oo-bundle-ds | converter, docservice, examples, metrics |

## Kubernetes Shape

One pod per app with sidecars. Containers in one pod share localhost and volumes.

```yaml
initContainers:
  - name: db
    image: <acr>/mw-app-db:<tag>
    restartPolicy: Always
    startupProbe:
      tcpSocket: {port: 5432}
containers:
  - name: app
    image: <acr>/mw-app-app:<tag>
    readinessProbe:
      tcpSocket: {port: 80}
volumes:
  - name: dbdata
    emptyDir: {}
```

For durable reset, replace emptyDir with a PVC created from VolumeSnapshot.

## Kueue and Gang Scheduling

- One podSet per app.
- Kueue Workload max is 8 podSets, so a 23-app slot is rendered as:
  - slot-<n>-g0: 8 podSets
  - slot-<n>-g1: 8 podSets
  - slot-<n>-g2: 7 podSets
- Shared Gateway is rendered once; slot HTTPRoutes attach across namespaces.
- ProvisioningRequest is optional because the external CRD is not always present.

## DSH Tracking Ledger

| Item | Status | Evidence |
|---|---|---|
| One-service Dockerfiles generated | In progress | docker/split/** |
| Snapshot DB generator | Fixed | SaaS-Bench f1df50b |
| Booklore snapshot DB build | Proven locally | mw-booklore-db:snapshot-test built |
| HRMS/prexit/twenty/opnform snapshots | Pending verified build | snapshot-build-summary.jsonl missing |
| apps.json sidecar conversion | Pending | unchanged until validated |
| Shared Gateway | Pushed | lumina-eval 362a913a |
| Kueue Workload chunking | Pushed | lumina-eval 9df10e9d |
| Native sidecar support | Pushed | lumina-eval 7d6f15ac |
| Liveness startup budget | Pushed | lumina-eval 78e07fe3 |
| AKS all-apps health | Partial | 16/23 Ready |
| SaaS-Bench verifier | Pending | use run_verify with Gateway hostname |

## Next Concrete Steps

1. Build snapshots serially and write snapshot-build-summary.jsonl.
2. Convert apps.json for booklore and hrms first.
3. Add PVC-from-snapshot mode in the slot manager renderer.
4. Validate reset by deleting and recreating a slot from snapshot.
5. Run run_verify on code-server/watcharr/twenty first, then all apps.
