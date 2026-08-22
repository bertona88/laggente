#!/bin/sh
set -eu

backup_root=${BACKUP_ROOT:-/backups}
uploads_root=${UPLOADS_ROOT:-/data/uploads}
archive_helper=${ARCHIVE_HELPER:-/opt/backup/archive-uploads.sh}
mode=${1:-}

list_backups() {
    find "$backup_root" -mindepth 1 -maxdepth 1 -type d -name '20??????T??????Z' | sort |
        while IFS= read -r backup_dir; do
            [ -n "$backup_dir" ] && basename "$backup_dir"
        done
}

validate_backup_id() {
    case "$1" in
        20??????T??????Z) ;;
        *) echo 'backup: backup id must be YYYYMMDDTHHMMSSZ' >&2; exit 64 ;;
    esac
}

verify_backup() {
    backup_id=$1
    validate_backup_id "$backup_id"
    backup_dir="$backup_root/$backup_id"
    [ -d "$backup_dir" ] || {
        echo "backup: set not found: $backup_id" >&2
        exit 66
    }
    (
        cd "$backup_dir"
        [ -f manifest.json ] || {
            echo 'backup: manifest is missing' >&2
            exit 66
        }
        sha256sum -c SHA256SUMS
        pg_restore --list database.dump >/dev/null
        "$archive_helper" verify uploads.tar.gz
    )
    echo "backup: verified $backup_id"
}

case "$mode" in
    list)
        list_backups
        exit 0
        ;;
    latest)
        latest_backup=$(list_backups | tail -n 1)
        [ -n "$latest_backup" ] || {
            echo 'backup: no completed logical backup exists' >&2
            exit 66
        }
        printf '%s\n' "$latest_backup"
        exit 0
        ;;
    verify)
        verify_backup "${2:-}"
        exit 0
        ;;
    once|daemon) ;;
    *)
        echo 'usage: backup.sh {once|daemon|list|latest|verify BACKUP_ID}' >&2
        exit 64
        ;;
esac

require_value() {
    variable_name=$1
    eval "variable_value=\${$variable_name:-}"
    if [ -z "$variable_value" ]; then
        echo "backup: required variable $variable_name is missing" >&2
        exit 64
    fi
}

require_value POSTGRES_USER
require_value POSTGRES_PASSWORD
require_value POSTGRES_DB

export PGHOST="${PGHOST:-db}"
export PGPORT="${PGPORT:-5432}"
export PGUSER="$POSTGRES_USER"
export PGPASSWORD="$POSTGRES_PASSWORD"
export PGDATABASE="$POSTGRES_DB"

retention_days=${BACKUP_RETENTION_DAYS:-14}
keep_minimum=${BACKUP_KEEP_MINIMUM:-7}
interval_seconds=${BACKUP_INTERVAL_SECONDS:-86400}
retry_seconds=${BACKUP_RETRY_SECONDS:-900}

case "$retention_days:$keep_minimum:$interval_seconds:$retry_seconds" in
    *[!0-9:]*|:*|*::*|*:)
        echo "backup: retention and interval settings must be positive integers" >&2
        exit 64
        ;;
esac
if [ "$retention_days" -lt 1 ] || [ "$keep_minimum" -lt 1 ] || \
   [ "$interval_seconds" -lt 60 ] || [ "$retry_seconds" -lt 60 ]; then
    echo "backup: retention/keep must be at least 1 and intervals at least 60 seconds" >&2
    exit 64
fi

prune_backups() {
    current_epoch=$(date +%s)
    keep_seconds=$((retention_days * 86400))
    backup_count=$(find "$backup_root" -mindepth 1 -maxdepth 1 -type d -name '20??????T??????Z' | wc -l | tr -d ' ')

    find "$backup_root" -mindepth 1 -maxdepth 1 -type d -name '20??????T??????Z' | sort | while IFS= read -r candidate; do
        [ -n "$candidate" ] || continue
        if [ "$backup_count" -le "$keep_minimum" ]; then
            break
        fi

        candidate_name=$(basename "$candidate")
        case "$candidate_name" in
            20??????T??????Z) ;;
            *) continue ;;
        esac

        modified_epoch=$(stat -c %Y "$candidate")
        age_seconds=$((current_epoch - modified_epoch))
        if [ "$age_seconds" -gt "$keep_seconds" ]; then
            echo "backup: pruning expired set $candidate_name"
            rm -rf -- "$candidate"
            backup_count=$((backup_count - 1))
        fi
    done
}

abort_backup() {
    status=$1
    shift
    printf 'backup: %s\n' "$*" >&2
    exit "$status"
}

run_backup() (
    # POSIX shells may suppress `set -e` throughout a function used as an `if` condition. The
    # daemon deliberately tests this function to choose its retry delay, so every capture and
    # publication step propagates failure explicitly instead of relying on errexit.
    mkdir -p "$backup_root" || abort_backup $? "cannot create backup root $backup_root"
    exec 9>"$backup_root/.backup.lock" || abort_backup $? 'cannot open backup lock'
    if ! flock -n 9; then
        echo "backup: another backup is already running" >&2
        exit 75
    fi

    timestamp=$(date -u +%Y%m%dT%H%M%SZ) || abort_backup $? 'cannot create backup timestamp'
    partial_dir="$backup_root/.partial-$timestamp-$$"
    final_dir="$backup_root/$timestamp"
    success_marker_tmp="$backup_root/.last_success_epoch.$$.tmp"
    database_dump="$partial_dir/database.dump"
    uploads_archive="$partial_dir/uploads.tar.gz"

    if [ -e "$final_dir" ]; then
        echo "backup: target already exists: $final_dir" >&2
        exit 73
    fi

    cleanup_partial() {
        if [ -n "${partial_dir:-}" ] && [ -d "$partial_dir" ]; then
            rm -rf -- "$partial_dir" || true
        fi
        if [ -n "${success_marker_tmp:-}" ] && [ -e "$success_marker_tmp" ]; then
            rm -f -- "$success_marker_tmp" || true
        fi
    }
    trap cleanup_partial EXIT HUP INT TERM

    mkdir -m 0700 "$partial_dir" || abort_backup $? 'cannot create partial backup directory'
    echo "backup: starting database snapshot $timestamp"
    pg_dump \
        --format=custom \
        --compress=6 \
        --no-owner \
        --no-privileges \
        --file="$database_dump" || abort_backup $? 'database snapshot failed'
    pg_restore --list "$database_dump" >/dev/null || \
        abort_backup $? 'database snapshot structural check failed'

    echo "backup: archiving private uploads"
    if [ -d "$uploads_root" ]; then
        "$archive_helper" create "$uploads_root" "$uploads_archive" || \
            abort_backup $? 'private upload archive failed'
    else
        mkdir "$partial_dir/empty-uploads" || \
            abort_backup $? 'cannot create empty upload staging directory'
        "$archive_helper" create "$partial_dir/empty-uploads" "$uploads_archive" || \
            abort_backup $? 'empty private upload archive failed'
        rmdir "$partial_dir/empty-uploads" || \
            abort_backup $? 'cannot remove empty upload staging directory'
    fi

    (
        cd "$partial_dir" &&
        sha256sum database.dump uploads.tar.gz >SHA256SUMS
    ) || abort_backup $? 'backup checksum generation failed'

    database_bytes=$(stat -c %s "$database_dump") || \
        abort_backup $? 'cannot measure database snapshot'
    uploads_bytes=$(stat -c %s "$uploads_archive") || \
        abort_backup $? 'cannot measure private upload archive'
    created_epoch=$(date +%s) || abort_backup $? 'cannot create backup success timestamp'
    printf '{"created_at":"%s","database":"%s","database_bytes":%s,"uploads_bytes":%s,"format":1}\n' \
        "$timestamp" "$POSTGRES_DB" "$database_bytes" "$uploads_bytes" \
        >"$partial_dir/manifest.json" || abort_backup $? 'backup manifest creation failed'

    chmod 0400 \
        "$partial_dir/database.dump" \
        "$partial_dir/uploads.tar.gz" \
        "$partial_dir/SHA256SUMS" \
        "$partial_dir/manifest.json" || abort_backup $? 'cannot protect backup payloads'
    printf '%s\n' "$created_epoch" >"$success_marker_tmp" || \
        abort_backup $? 'cannot stage backup success marker'
    chmod 0600 "$success_marker_tmp" || abort_backup $? 'cannot protect backup success marker'
    mv "$partial_dir" "$final_dir" || abort_backup $? 'cannot publish completed backup set'
    mv "$success_marker_tmp" "$backup_root/.last_success_epoch" || {
        status=$?
        rm -rf -- "$final_dir" || true
        abort_backup "$status" 'cannot publish backup success marker'
    }
    trap - EXIT HUP INT TERM

    prune_backups
    echo "backup: completed $timestamp"
)

case "$mode" in
    once)
        run_backup
        ;;
    daemon)
        while :; do
            if run_backup; then
                sleep "$interval_seconds"
            else
                echo "backup: attempt failed; retrying in $retry_seconds seconds" >&2
                sleep "$retry_seconds"
            fi
        done
        ;;
esac
