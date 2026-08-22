#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=production-lib.sh
source "$script_dir/production-lib.sh"

release_id=
git_sha=
api_image=
gateway_image=
backup_image=
build_on_host=false
allow_mutable_images=false

usage() {
    cat <<'EOF'
Usage:
  ./scripts/deploy-production.sh --release ID --git-sha SHA \
    --api-image IMAGE --gateway-image IMAGE --backup-image IMAGE

Initial-only fallback (builds on the 4 GB production host):
  ./scripts/deploy-production.sh --release ID --git-sha SHA --build-on-host

Published images must normally use immutable @sha256: digests. Database migrations
are not reversed automatically; deploy backward-compatible migrations.
EOF
}

while (($#)); do
    case "$1" in
        --release) release_id=${2:?missing release id}; shift 2 ;;
        --git-sha) git_sha=${2:?missing git SHA}; shift 2 ;;
        --api-image) api_image=${2:?missing api image}; shift 2 ;;
        --gateway-image) gateway_image=${2:?missing gateway image}; shift 2 ;;
        --backup-image) backup_image=${2:?missing backup image}; shift 2 ;;
        --build-on-host) build_on_host=true; shift ;;
        --allow-mutable-images) allow_mutable_images=true; shift ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown option: $1" ;;
    esac
done

[[ -n "$release_id" ]] || die "--release is required"
[[ -n "$git_sha" ]] || die "--git-sha is required"
validate_release_id "$release_id"
[[ "$git_sha" =~ ^[0-9a-f]{40}$ ]] || die "--git-sha must be a full 40-character lowercase SHA"

require_command docker
require_command curl
require_command flock
configure_docker_client
require_repo
require_secret_files
assert_capacity 4194304

mkdir -p "$laggente_releases_dir"
exec 9>"$laggente_root/deploy.lock"
flock -n 9 || die "another LAGGENTE deployment is running"

candidate_env="$laggente_releases_dir/$release_id.env"
current_env="$laggente_releases_dir/current.env"
require_unused_release_path "$candidate_env"
previous_env=
if [[ -e "$current_env" ]]; then
    previous_env=$(readlink -f "$current_env")
fi

if [[ "$build_on_host" == true ]]; then
    api_image="laggente-api:$release_id"
    gateway_image="laggente-gateway:$release_id"
    backup_image="laggente-backup:$release_id"
else
    [[ -n "$api_image" && -n "$gateway_image" && -n "$backup_image" ]] || \
        die "all three image references are required unless --build-on-host is used"
    if [[ "$allow_mutable_images" != true ]]; then
        for image_ref in "$api_image" "$gateway_image" "$backup_image"; do
            [[ "$image_ref" == *@sha256:* ]] || die "mutable image reference refused: $image_ref"
        done
    fi
fi

umask 027
candidate_tmp=$(mktemp "$laggente_releases_dir/.candidate.XXXXXX")
trap 'rm -f -- "${candidate_tmp:-}"' EXIT
printf '%s\n' \
    "LAGGENTE_RELEASE=$release_id" \
    "LAGGENTE_GIT_SHA=$git_sha" \
    "LAGGENTE_API_IMAGE=$api_image" \
    "LAGGENTE_GATEWAY_IMAGE=$gateway_image" \
    "LAGGENTE_BACKUP_IMAGE=$backup_image" \
    "LAGGENTE_DATABASE_ENV_FILE=$laggente_database_env_file" \
    "LAGGENTE_APPLICATION_ENV_FILE=$laggente_application_env_file" \
    "LAGGENTE_DATA_ROOT=$laggente_root/data" \
    "LAGGENTE_LOOPBACK_PORT=$laggente_loopback_port" \
    >"$candidate_tmp"
mv "$candidate_tmp" "$candidate_env"
trap - EXIT

note "validating Compose configuration"
compose_with_release "$candidate_env" config --quiet

if [[ -n "$previous_env" ]]; then
    if ! compose_with_release "$previous_env" ps --status running backup | grep -q backup; then
        die "an existing release has no running backup service; refusing to migrate"
    fi
    note "creating pre-migration logical backup"
    compose_with_release "$previous_env" exec -T backup /opt/backup/backup.sh once
fi

if [[ "$build_on_host" == true ]]; then
    note "building release images on host; this is the initial-only low-memory fallback"
    export COMPOSE_PARALLEL_LIMIT=1
    for service in api gateway backup; do
        compose_with_release "$candidate_env" build --pull "$service"
    done
else
    note "pulling immutable application images"
    compose_with_release "$candidate_env" pull api gateway backup
fi
# PostgreSQL and the data-init base are stateful foundation images, not application-release
# artifacts. Compose may fetch them when genuinely absent on first bootstrap, but an ordinary app
# deploy must not silently move their mutable tags. Upgrade them only through the runbook.

note "starting PostgreSQL"
compose_with_release "$candidate_env" up -d db

note "running Alembic migrations"
compose_with_release "$candidate_env" run --rm migrate

rollback_application() {
    local exit_status=${1:-$?}
    trap - ERR HUP INT TERM
    printf 'deployment failed after migration; database restore is intentionally not automatic\n' >&2
    if [[ -n "$previous_env" && -f "$previous_env" ]]; then
        printf 'returning application containers to the previous release\n' >&2
        compose_with_release "$previous_env" up -d --no-build --remove-orphans db api gateway backup || true
    else
        compose_with_release "$candidate_env" stop gateway api backup || true
    fi
    compose_with_release "$candidate_env" logs --tail 120 api gateway || true
    exit "$exit_status"
}
trap rollback_application ERR
trap 'rollback_application 129' HUP
trap 'rollback_application 130' INT
trap 'rollback_application 143' TERM

note "activating application containers"
compose_with_release "$candidate_env" up -d --no-build --remove-orphans db api gateway backup
if ! wait_for_gateway; then
    printf 'gateway did not become healthy\n' >&2
    rollback_application 1
fi

if [[ -n "$previous_env" ]]; then
    ln -sfn "$(basename "$previous_env")" "$laggente_releases_dir/previous.env"
fi
ln -sfn "$(basename "$candidate_env")" "$current_env"
trap - ERR HUP INT TERM

note "release $release_id is active"
compose_with_release "$candidate_env" ps
