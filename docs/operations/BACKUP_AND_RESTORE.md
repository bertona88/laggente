# Backup and Restore

## What is backed up

The `backup` container runs immediately at startup and then every 24 hours by default. Each set contains:

```text
/opt/laggente/data/backups/YYYYMMDDTHHMMSSZ/
  database.dump
  uploads.tar.gz
  SHA256SUMS
  manifest.json
```

- `database.dump` is an internally consistent PostgreSQL custom-format snapshot created by `pg_dump` and structurally checked by `pg_restore --list`.
- `uploads.tar.gz` is a private filesystem archive of durable image attachments and documents. Recognized raw-audio extensions and temporary paths are excluded as defense in depth, then the completed archive is checked for forbidden entries. It is readable only by the backup/runtime identity.
- `SHA256SUMS` protects both payloads against silent corruption.
- A completed set becomes visible only after its temporary directory is atomically renamed.

The default retention is 14 days with a minimum of seven completed sets. Retention only removes timestamp-shaped directories inside the dedicated backup mount. It never touches another project's data.

`pg_dump` completes before the live upload tree is archived. The two payloads are therefore
individually verifiable but are not a cross-store atomic snapshot: a private file created or deleted
between those steps can leave a database row and archive entry out of alignment. This is an
accepted controlled-pilot recovery caveat, not a claim of full application consistency. Do not run
a deliberate attachment/document deletion, manual retention purge, or data repair during a backup. The API
also applies retention automatically every six hours after its startup grace, so a completed set
must still be treated as potentially cross-store non-atomic until writer quiescence or
reconciliation is implemented. Before calling
a backup fully file-consistent, either quiesce all application writers for the entire capture
or add and verify a reconciliation manifest that maps the dump's attachment and document records to archived
files. The current `manifest.json` records set metadata and sizes; it is not that reconciliation.

## Important boundary

These logical backups are initially on the same server disk. They protect against application mistakes and support point-in-time operator recovery, but they do not protect against loss of the entire VPS or disk. Before public launch, enable Hetzner provider backups or copy the completed backup sets to an independently controlled off-host destination. A provider snapshot complements `pg_dump`; it does not replace it.

Capacity planning must include full-copy amplification. One account held at the 512 MiB combined
durable-image-and-document ceiling can contribute about 7 GiB of upload payload across 14 full local backup sets
(`14 × 512 MiB = 7168 MiB`), before the live upload tree, database dumps, manifests, container
images, build cache, or additional accounts. Compression may reduce physical use but must not be
assumed when reserving space. Independently sized Hetzner provider or off-host capacity remains a
launch requirement; increasing local disk alone does not provide disk-loss protection.

## Routine checks

```bash
cd /opt/laggente/repo
./scripts/audit-production.sh

current_env=/opt/laggente/releases/current.env
docker compose --env-file "$current_env" ps backup
docker compose --env-file "$current_env" logs --tail 100 backup
docker compose --env-file "$current_env" exec -T backup \
  /opt/backup/backup.sh list
```

The backup health check becomes unhealthy when no successful set exists or the last success is older than the configured interval plus six hours.

## Take a backup now

Run before every migration and before any deliberate data repair:

```bash
cd /opt/laggente/repo
./scripts/backup-now.sh
```

Wait for the command to complete before beginning the migration or repair; do not overlap an
attachment deletion or purge with the capture.

The release script invokes the same operation before migrations when a prior release is running. A first deployment has no earlier database to protect.

## Restore rehearsal

Never make the production database the first place a dump is tested. The verification script starts a temporary PostgreSQL service on an internal-only Compose network and tmpfs, restores the dump, checks public tables and the upload archive, and then removes the temporary project.

```bash
cd /opt/laggente/repo
backup_id=$(docker compose --env-file "$current_env" exec -T backup \
  /opt/backup/backup.sh latest)
./scripts/verify-backup-restore.sh "$backup_id"
```

Record the backup ID, rehearsal time, result, and application release in the launch/change record. Run at least one successful rehearsal before the pilot is considered recoverable, then repeat periodically and before a risky migration.

## Restore private uploads only

Stop application writers, validate the archive, and extract into a separate recovery directory first:

```bash
cd /opt/laggente/repo
current_env=/opt/laggente/releases/current.env
backup_id=REPLACE_WITH_VERIFIED_BACKUP_ID

./scripts/verify-backup-restore.sh "$backup_id"
docker compose --env-file "$current_env" stop gateway api backup
case "$backup_id" in 20??????T??????Z) ;; *) exit 64 ;; esac
sudo sh -ec '
  backup_id=$1
  cd "/opt/laggente/data/backups/$backup_id"
  sha256sum -c SHA256SUMS
  install -d -m 0700 /opt/laggente/data/uploads-recovery
  tar -xzf uploads.tar.gz -C /opt/laggente/data/uploads-recovery
' sh "$backup_id"
```

The root step is deliberate: rootless containers own bind-mounted backup payloads through subordinate UIDs, so the ordinary `laggente` host user must not inspect them directly. The archive contains durable image attachments and documents; raw-audio extensions and temporary paths are excluded and verified inside the backup container. Inspect the recovery tree before deliberately exchanging it with `/opt/laggente/data/uploads`. Keep the previous upload directory intact until the application and authorization checks pass. Do not merge archives blindly into the live tree.

## Full database recovery

This is a deliberate last-resort operation requiring a maintenance window and human approval. Normal application rollback does not restore PostgreSQL.

1. Select a backup that passed the isolated rehearsal.
2. Record the active release and take a fresh safety backup if the current database is readable.
3. Stop all LAGGENTE writers, leaving the database running:

   ```bash
   cd /opt/laggente/repo
   current_env=/opt/laggente/releases/current.env
   docker compose --env-file "$current_env" stop gateway api backup
   ```

4. Create a separate recovery database and restore into it. Do not drop or overwrite the current database:

   ```bash
   backup_id=REPLACE_WITH_VERIFIED_BACKUP_ID
   docker compose --env-file "$current_env" exec -T db \
     sh -ec 'createdb -U "$POSTGRES_USER" laggente_recovery'
   docker compose --env-file "$current_env" run --rm --no-deps \
     -e BACKUP_ID="$backup_id" backup \
     sh -ec 'pg_restore \
       --host=db \
       --username="$POSTGRES_USER" \
       --dbname=laggente_recovery \
       --exit-on-error \
       --no-owner \
       --no-privileges \
       "/backups/$BACKUP_ID/database.dump"'
   ```

5. Inspect the recovery database from the backup container and compare expected table counts. If it is not correct, drop only `laggente_recovery` and leave production unchanged.
6. In a separately reviewed command window, terminate LAGGENTE connections and atomically rename the current database to a timestamped hold name, then rename `laggente_recovery` to the configured `POSTGRES_DB`. Never use `DROP DATABASE` for this exchange.
7. Run `alembic upgrade head` against the recovered database with the intended application release, start services, and complete server plus browser acceptance checks.
8. Keep the held pre-restore database until recovery is accepted and another restore-tested backup exists. Its deletion is a separate destructive decision.

The database exchange in step 6 is intentionally not encoded as a one-command script. It is rare, destructive if aimed at the wrong database, and must be written against freshly verified database names and connection state.

## Recovery acceptance

A recovery is accepted only when:

- the selected dump and upload archive checksums pass;
- an isolated restore rehearsal succeeds;
- the cross-store consistency status is recorded; claim full private-file consistency only when
  attachment/document rows and archived files were reconciled or the set was captured with application
  writers quiesced, otherwise keep the controlled-pilot caveat explicit;
- migrations complete against the recovered database;
- the loopback gateway, public hosts, authentication, Studio, public conversation, activation boundary, and human join flow pass;
- cross-account and visitor-continuation denial tests pass;
- a new logical backup of the recovered production state succeeds and itself passes restore rehearsal;
- the old database or upload tree remains available until explicit cleanup approval.
