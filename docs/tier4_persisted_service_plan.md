# Tier 4 Persisted Service Plan
## Implemented Tier 4 DB Layer

Implemented and validated in `saas-bench-slot-4`:

- CloudNativePG installed in `cnpg-system`.
- MariaDB Operator installed in `mariadb-system`.
- Shared PostgreSQL cluster `tier4-pg` created via CNPG.
- Shared MariaDB cluster `tier4-mariadb` created via MariaDB Operator.
- PostgreSQL databases and owners created for:
  - baserow, mattermost, openproject, opnform, pretix, twenty, mediacms
- MariaDB databases/users/grants created for:
  - bigcapital, booklore, hrms, openemr, owncloud, photoprism, roundcubemail, onlyoffice
- Measured Tier 4 DB-layer readiness: `67.1s` for both operators' clusters.
- Manifest: `docs/tier4/slot4-db-layer.yaml`

Not yet implemented:

- App workloads are not wired to the shared DB services yet.
- Redis, Elasticsearch, RabbitMQ, and MSSQL layers are not installed.
- File-backed Tier 2 apps use the persisted-service overlay and still need PVC snapshot validation in a fresh slot.


## File-Backed DB Findings

Confirmed from live pods:

| App | Current storage | Can use file-backed DB? | Recommended tier |
|---|---|---|---|
| grocy | SQLite `/config/data/grocy.db` | Yes, already file-backed | PVC + VolumeSnapshot |
| metabase | H2 file `/metabase-data/metabase.db` | Yes, already file-backed | PVC + VolumeSnapshot |
| siyuan | SQLite `/siyuan/workspace/temp/*.db` | Yes, already file-backed | PVC + VolumeSnapshot |
| watcharr | SQLite `/data/watcharr.db` | Yes, already file-backed | PVC + VolumeSnapshot |
| farmOS | SQLite `/opt/drupal/web/sites/default/files/.ht.sqlite` | Yes, already file-backed | PVC + VolumeSnapshot |
| PhotoPrism | currently MySQL; binary supports `sqlite` and `mysql` | Yes, SQLite is the default driver | Prefer SQLite + PVC for Tier 4 |
| recipya | config + Database directory; likely SQLite | Needs one final file check | Likely PVC + VolumeSnapshot |
| Roundcube | currently MySQL DSN | Roundcube supports SQLite DSN, but migration/config change needed | DB operator unless SQLite migration is accepted |
| e-label | MSSQL Express env detected | No, it is MSSQL-backed | Needs MSSQL strategy, not SQLite |
| MediaCMS | PostgreSQL only in image config | No, image is Postgres-backed | CNPG |
| Baserow | PostgreSQL only | No | CNPG |
| BigCapital | MySQL | No | MariaDB/MySQL operator |
| Booklore | MariaDB | No | MariaDB operator |
| HRMS | MariaDB + Redis | No | MariaDB + Redis operator |
| Mattermost | PostgreSQL + Bleve files | No for DB; file for Bleve | CNPG + PVC |
| OnlyOffice | MySQL + Elasticsearch + Redis + cache | No | MariaDB + ES + Redis/RabbitMQ |
| OpenEMR | MariaDB | No | MariaDB operator |
| OpenProject | PostgreSQL + assets | No for DB; files need PVC | CNPG + PVC |
| OpnForm | PostgreSQL + Redis | No | CNPG + Redis |
| ownCloud | MariaDB + Redis + data | No | MariaDB + Redis + PVC |
| Pretix | PostgreSQL + Redis + data | No | CNPG + Redis + PVC |
| Twenty | PostgreSQL + Redis | No | CNPG + Redis |

Conclusion:

- File-backed DB apps should not get a DB operator. They should use PVC + VolumeSnapshot reset.
- SQL-required apps need operators.
- PhotoPrism should be moved to SQLite to avoid MariaDB.
- Roundcube can be moved to SQLite only if we accept a config/migration change; otherwise it stays on MariaDB.
- e-label is an MSSQL exception and needs its own path.
- MediaCMS is PostgreSQL-only in this image and needs CNPG.

Revised Tier 4 split:

```text
TIER 2 PVC snapshot:
  grocy, metabase, siyuan, watcharr, farmOS, recipya, code-server,
  Mattermost Bleve, OpenProject assets, ownCloud data, Pretix data,
  PhotoPrism originals/cache

TIER 4 DB operator:
  Baserow, BigCapital, Booklore, HRMS, Mattermost, OpenEMR,
  OpenProject, OpnForm, ownCloud, Pretix, Twenty, OnlyOffice,
  MediaCMS, e-label (MSSQL exception)
```


Status: planning only. No slot-manager changes. No app wiring yet.

## Current Spike State

- CloudNativePG (CNPG) operator installed in `cnpg-system`.
- A spike CNPG cluster was created in namespace `saas-bench-slot-4`:
  - `openproject-db`
  - 1 instance
  - database `openproject`, owner `openproject`
  - became Ready in 234.7s
- No fake-app workload in slot 4 has been switched to the operator-managed DB yet.
- Slot 0 and slot 1 were not modified.

## Tier 4 Architecture Decision

Recommended Tier 4 shape for test slots:

- **Shared operator-managed DB layer per slot**, with database/schema isolation per app.
- One PostgreSQL cluster per slot via CNPG.
- One MariaDB/MySQL cluster per slot via a MariaDB operator.
- One Redis service per slot via a Redis operator or dedicated StatefulSet.
- One Elasticsearch/OpenSearch service per slot only if OnlyOffice remains in scope.
- One RabbitMQ service per slot only if OnlyOffice remains in scope.
- File-backed state remains on PVCs with VolumeSnapshot for code-server workspaces, Mattermost Bleve indexes, OpenProject assets, ownCloud data, Pretix data, etc.

Why shared-per-slot:

- Fewer DB pods than one cluster per app.
- Slot provisioning and teardown are simpler.
- Schema/database isolation gives enough separation for benchmark slots.
- Failures are contained to a slot, not a shared global DB.

Tradeoff:

- A DB outage takes down every app in that slot.
- Per-app clusters are safer but much more expensive and slower to provision.
- Shared global DBs are cheaper but create cross-slot blast radius and should not be used for benchmark reset.

## Persisted Service Inventory

| App | Persisted services | Operator target | Status |
|---|---|---|---|
| baserow | PostgreSQL, Redis, data volume | CNPG + Redis | Confirmed by split Dockerfiles |
| bigcapital | MySQL, Redis | MariaDB operator + Redis | Confirmed by split Dockerfiles |
| booklore | MariaDB | MariaDB operator | Confirmed; snapshot reset already validated |
| code-server | workspace files | PVC + VolumeSnapshot | Confirmed filesystem-only |
| e-label | unknown | verify image | Needs inspection |
| farmos | verify DB engine | verify image | Needs inspection |
| grocy | SQLite/file DB likely | PVC + VolumeSnapshot | Needs confirmation |
| hrms | MariaDB, Redis | MariaDB operator + Redis | Confirmed |
| mattermost | PostgreSQL, Bleve index, config/data/logs | CNPG + PVC | Confirmed |
| mediacms | verify DB/index | verify image | Needs inspection |
| metabase | embedded H2 DB likely | PVC + VolumeSnapshot or app DB | Needs confirmation |
| onlyoffice | MySQL, Elasticsearch, Redis, DS cache, possibly RabbitMQ | MariaDB + ECK/OpenSearch + Redis + RabbitMQ | Confirmed for MySQL/ES/Redis |
| openemr | MariaDB | MariaDB operator | Confirmed by split Dockerfile |
| openproject | PostgreSQL, assets | CNPG + PVC | Confirmed |
| opnform | PostgreSQL, Redis | CNPG + Redis | Confirmed |
| owncloud | MariaDB, Redis, ownCloud data | MariaDB + Redis + PVC | Confirmed |
| photoprism | MariaDB, originals/cache | MariaDB + PVC | Confirmed DB; file paths need review |
| pretix | PostgreSQL, Redis, pretix data | CNPG + Redis + PVC | Confirmed |
| recipya | SQLite likely | PVC + VolumeSnapshot | Needs confirmation |
| roundcubemail | MariaDB, mail data | MariaDB + PVC/mail store | Confirmed DB |
| siyuan | SQLite/workspace files | PVC + VolumeSnapshot | Needs confirmation |
| twenty | PostgreSQL, Redis | CNPG + Redis | Confirmed |
| watcharr | SQLite | PVC + VolumeSnapshot | Needs confirmation |

## Operator Set

Minimum safe set for full Tier 4:

1. CloudNativePG for PostgreSQL.
2. MariaDB Operator for MariaDB/MySQL.
3. Redis operator or a hardened StatefulSet with PVCs.
4. Elastic Cloud on Kubernetes (ECK) or OpenSearch Operator for OnlyOffice.
5. RabbitMQ Cluster Operator if OnlyOffice needs RabbitMQ.
6. CSI VolumeSnapshot for file-backed state.

## Required Metadata Per App

Add explicit Tier 4 metadata before implementation:

```json
{
  "resetStrategy": "operator",
  "db": {
    "engine": "postgres|mariadb|mysql|redis|elasticsearch|file",
    "database": "app_slot_database",
    "owner": "app_user",
    "service": "slot-pg-rw"
  }
}
```

The slot manager should not guess DB engines from image names.

## Rollout Phases

1. Finish inventory.
   - Inspect e-label, farmos, mediacms, metabase, grocy, recipya, siyuan, watcharr.
   - Confirm exact DB/file paths and connection envs.

2. Install operators.
   - CNPG: installed.
   - MariaDB operator.
   - Redis operator/StatefulSet.
   - ECK/OpenSearch if OnlyOffice stays.
   - RabbitMQ if OnlyOffice stays.

3. Add manifest overlay.
   - Keep current sidecar manifests as Tier 3.
   - Add operator-backed manifests for Tier 4.
   - App containers connect to slot DB services instead of localhost.
   - DB sidecars are removed in Tier 4 mode.

4. Provision slot 4.
   - Create `saas-bench-slot-4`.
   - Create shared operator DB clusters.
   - Create per-app databases/users.
   - Deploy app containers pointing at operator services.
   - Create PVCs for file-backed state.

5. Measure.
   - DB layer ready time.
   - App ready time.
   - Full slot provision time.
   - Reset time.

6. Add reset/quarantine.
   - Reset operator-backed DBs by dropping/recreating app database or restoring snapshot.
   - Reset file PVCs from VolumeSnapshot.
   - Mark slot unhealthy/timeout on failure.
   - Exclude quarantined slots from admission.

## Risks

- Shared DB cluster outage takes down the whole slot.
- Operator CRDs and versions add upgrade risk.
- OnlyOffice’s ES and RabbitMQ stack is the heaviest part.
- File-backed state still needs VolumeSnapshot; operators do not solve it.
- Several apps need DB URL/env changes, not just DB replacement.
- MariaDB apps use different auth models: some need root TCP, some need app users.
- Operator-managed DB restore semantics differ from app-native reset.
- Provision time may be dominated by image pulls, not DB startup.

## Immediate Next Step

Do not wire app workloads yet. First finish the unknown inventory and choose the MariaDB/Redis/ES operator set. Then create the Tier 4 overlay and test with one Postgres app and one MariaDB app before provisioning the full slot 4.
