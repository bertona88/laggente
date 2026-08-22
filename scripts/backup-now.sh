#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=production-lib.sh
source "$script_dir/production-lib.sh"

configure_docker_client
require_repo
current_env="$laggente_releases_dir/current.env"
[[ -e "$current_env" ]] || die "no active production release"

compose_with_release "$current_env" exec -T backup /opt/backup/backup.sh once
