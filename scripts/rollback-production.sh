#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=production-lib.sh
source "$script_dir/production-lib.sh"

target_release=${1:-}
[[ -n "$target_release" ]] || die "usage: rollback-production.sh RELEASE_ID"
validate_release_id "$target_release"

require_command docker
require_command curl
require_command flock
configure_docker_client
require_repo
require_secret_files

target_env="$laggente_releases_dir/$target_release.env"
current_env="$laggente_releases_dir/current.env"
[[ -f "$target_env" ]] || die "release environment not found: $target_env"
[[ -e "$current_env" ]] || die "no current release is recorded"
old_current=$(readlink -f "$current_env")

exec 9>"$laggente_root/deploy.lock"
flock -n 9 || die "another LAGGENTE deployment is running"

note "taking a logical backup before application rollback"
compose_with_release "$old_current" exec -T backup /opt/backup/backup.sh once

restore_current() {
    local exit_status=${1:-$?}
    trap - ERR HUP INT TERM
    printf 'rollback failed; restoring the previously active application images\n' >&2
    compose_with_release "$old_current" up -d --no-build --remove-orphans db api gateway backup || true
    exit "$exit_status"
}
trap restore_current ERR
trap 'restore_current 129' HUP
trap 'restore_current 130' INT
trap 'restore_current 143' TERM

note "activating application release $target_release without reversing database migrations"
compose_with_release "$target_env" up -d --no-build --remove-orphans db api gateway backup
if ! wait_for_gateway; then
    printf 'rolled-back application did not become healthy\n' >&2
    restore_current 1
fi

ln -sfn "$(basename "$old_current")" "$laggente_releases_dir/previous.env"
ln -sfn "$(basename "$target_env")" "$current_env"
trap - ERR HUP INT TERM
note "application rollback completed"
