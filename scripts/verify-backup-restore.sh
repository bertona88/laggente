#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=production-lib.sh
source "$script_dir/production-lib.sh"

backup_id=${1:-}
[[ "$backup_id" =~ ^20[0-9]{6}T[0-9]{6}Z$ ]] || \
    die "usage: verify-backup-restore.sh YYYYMMDDTHHMMSSZ"

configure_docker_client
require_repo
current_env="$laggente_releases_dir/current.env"
[[ -e "$current_env" ]] || die "no active production release"
compose_with_release "$current_env" exec -T backup \
    /opt/backup/backup.sh verify "$backup_id" >/dev/null

restore_project="laggente-restore-$(date -u +%Y%m%d%H%M%S)-$$"
cleanup() {
    compose_with_release "$current_env" -p "$restore_project" --profile restore down --volumes --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT HUP INT TERM

export RESTORE_DUMP="/backups/$backup_id/database.dump"
compose_with_release "$current_env" -p "$restore_project" --profile restore run --rm restore-verify
note "isolated restore verification passed for $backup_id"
