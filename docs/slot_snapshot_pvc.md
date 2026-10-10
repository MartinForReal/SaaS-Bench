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

## Reset Strategy Decision Matrix

Status: workstream 1 recommendation (2026-10-10)

### Strategy Comparison

| Strategy | Reset warmth | State safety | Complexity | Best fit |
|---|---|---|---|---|
| App-native reset | Warm | High when app exposes a verified reset endpoint | Medium per app | Tier 1 apps with real reset endpoints |
| PVC snapshot reset | Cold pod, fast DB boot | High after clean quiesce; risks torn snapshots if hot | Medium; CSI snapshot + PVC templates | Tier 2 persisted DB services |
| Kubernetes DB service/operator | Usually warm | High if operator owns backup/restore | High; adds operator and CRDs | Shared DB platform, not per-slot default |
| Schema/database-per-slot | Warm | Medium; app-level state may still leak | Medium | Multi-tenant DBs with no file-level reset |
| Full provision | Cold | Highest isolation | High resource cost | Tier 3 default and unknown apps |

### Recommended Reset Tiers

| Tier | Definition | Option B eligible? | Slot-manager behavior |
|---|---|---|---|
| Tier 1: native | App resets without recreating pod; warmth preserved | Yes | Call app reset endpoint or exec reset command |
| Tier 2: snapshot | Delete pod and PVC; StatefulSet recreates PVC from VolumeSnapshot | No, unless measured warm | Pod delete + PVC delete when resetStrategy=snapshot |
| Tier 3: provision | Delete and recreate full workload | No | Standard pod reset or full reprovision |

### Current Per-App Matrix

| App | Reset tier | Persisted state | Evidence / next proof |
|---|---|---|---|
| code-server | Tier 3 provision | workspace files | Pod reset works; PVC snapshot only if warm workspace reset is required |
| openproject | Tier 3 provision | PostgreSQL + assets | PostgreSQL sidecar migrates on boot; assets still need PVC snapshot for warm reset |
| metabase | Tier 3 provision | H2 file `/metabase-data/metabase.db` | File-backed; promote to Tier 2 only with PVC snapshot proof |
| baserow | Tier 3 provision | PostgreSQL + Redis | Bootstrap sidecar creates admin; DB reset still full provision |
| twenty | Tier 3 provision | PostgreSQL + Redis | Full provision until operator or snapshot reset is proven |
| bigcapital | Tier 3 provision | MySQL + Redis | Full provision until DB reset is proven |
| hrms | Tier 3 provision | MariaDB + Redis + files | Slot 1 DB user bootstrap proven; still full provision until snapshot/operator reset |
| pretix | Tier 3 provision | PostgreSQL + Redis + data | Full provision until DB/data reset is proven |
| openemr | Tier 3 provision | MariaDB | Full provision until DB reset is proven |
| opnform | Tier 3 provision | PostgreSQL + Redis | Full provision until DB reset is proven |
| onlyoffice | Tier 3 provision | MySQL + Elasticsearch + Redis/cache | Heaviest stack; full provision until operator reset is proven |
| mattermost | Tier 3 provision | PostgreSQL + Bleve files | Full provision; Bleve/config files need PVC snapshot if warm reset is desired |
| owncloud | Tier 3 provision | MariaDB + Redis + data | Full provision; data and DB reset still needed |
| roundcubemail | Tier 3 provision | MariaDB + mail data | Full provision; SQLite migration would change tier |
| grocy | Tier 3 provision | SQLite `/config/data/grocy.db` | Candidate Tier 2 PVC snapshot; proof pending |
| recipya | Tier 3 provision | SQLite/config + files | Candidate Tier 2 PVC snapshot; file path proof pending |
| farmos | Tier 3 provision | SQLite + Drupal files | Candidate Tier 2 PVC snapshot; proof pending |
| e-label | Tier 3 provision | MSSQL Express | Full provision until MSSQL reset strategy is proven |
| siyuan | Tier 3 provision | SQLite workspace | Candidate Tier 2 PVC snapshot; proof pending |
| watcharr | Tier 3 provision | SQLite `/data/watcharr.db` | Candidate Tier 2 PVC snapshot; proof pending |
| booklore | Tier 2 snapshot | MariaDB datadir | `booklore-golden-v5`; PVC recreated; slot reset returned ready; seeded split DB image committed as `8446498` |
| mediacms | Tier 3 provision | PostgreSQL + media files | Full provision until DB reset is proven |
| photoprism | Tier 3 provision | MariaDB or SQLite + originals/cache | Candidate Tier 2 PVC snapshot if moved to SQLite; proof pending |

### Controller Rules

- `resetStrategy` is explicit in `apps.json`.
- Default is `provision`; this preserves current pod-only reset behavior.
- PVC deletion happens only when:
  - `SAAS_BENCH_RESET_PVCS=1`
  - per-slot namespaces are enabled
  - the app's `resetStrategy` is `snapshot`
- Snapshot creation is not part of reset. Snapshots must be built and quiesced separately.
- A reset that times out or errors must remain quarantined for admission until a later verified reset succeeds.

### Snapshot Authoring Rules

- Stop the DB cleanly before taking the snapshot.
- Record snapshot name and app image tag together.
- Prefer deleting and recreating the StatefulSet when claim templates change.
- Keep one snapshot per app/image version and make rollback explicit.

