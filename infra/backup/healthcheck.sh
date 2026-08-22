#!/bin/sh
set -eu

last_success_file=/backups/.last_success_epoch
interval_seconds=${BACKUP_INTERVAL_SECONDS:-86400}
grace_seconds=${BACKUP_HEALTH_GRACE_SECONDS:-21600}

if [ ! -s "$last_success_file" ]; then
    echo "backup health: no completed backup marker" >&2
    exit 1
fi

last_success_epoch=$(cat "$last_success_file")
case "$last_success_epoch" in
    *[!0-9]*|'')
        echo "backup health: invalid completion marker" >&2
        exit 1
        ;;
esac

now_epoch=$(date +%s)
age_seconds=$((now_epoch - last_success_epoch))
maximum_age=$((interval_seconds + grace_seconds))

if [ "$age_seconds" -gt "$maximum_age" ]; then
    echo "backup health: last successful backup is $age_seconds seconds old" >&2
    exit 1
fi
