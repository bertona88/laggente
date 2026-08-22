#!/bin/sh
set -eu

if [ -z "${RESTORE_DUMP:-}" ]; then
    echo "restore verification: RESTORE_DUMP is required" >&2
    exit 64
fi

resolved_dump=$(realpath "$RESTORE_DUMP" 2>/dev/null || true)
case "$resolved_dump" in
    /backups/20??????T??????Z/database.dump) ;;
    *)
        echo "restore verification: dump must be /backups/<UTC timestamp>/database.dump" >&2
        exit 64
        ;;
esac

if [ ! -f "$resolved_dump" ]; then
    echo "restore verification: dump does not exist" >&2
    exit 66
fi

backup_dir=$(dirname "$resolved_dump")
(
    cd "$backup_dir"
    sha256sum -c SHA256SUMS
)
pg_restore --list "$resolved_dump" >/dev/null

echo "restore verification: restoring into isolated temporary PostgreSQL"
pg_restore \
    --clean \
    --if-exists \
    --exit-on-error \
    --no-owner \
    --no-privileges \
    --dbname="$PGDATABASE" \
    "$resolved_dump"

table_count=$(psql --no-psqlrc --tuples-only --no-align --command="SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';")
case "$table_count" in
    ''|*[!0-9]*)
        echo "restore verification: invalid table-count result" >&2
        exit 1
        ;;
esac
if [ "$table_count" -lt 1 ]; then
    echo "restore verification: restored database has no public tables" >&2
    exit 1
fi

uploads_archive="$backup_dir/uploads.tar.gz"
if [ -f "$uploads_archive" ]; then
    /opt/backup/archive-uploads.sh verify "$uploads_archive"
fi

echo "restore verification: passed ($table_count public tables)"
