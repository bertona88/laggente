#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=production-lib.sh
source "$script_dir/production-lib.sh"

configure_docker_client
require_repo
require_command jq
current_env="$laggente_releases_dir/current.env"
[[ -e "$current_env" ]] || die "no active production release"

printf 'LAGGENTE production audit (read-only)\n'
printf 'host: '; hostname
printf 'uptime: '; uptime
free -h
df -h "$laggente_root"

require_secret_files
printf 'database/application secrets: present, split, and permission-restricted\n'

compose_with_release "$current_env" ps

published=$(compose_service_published_bindings "$current_env" gateway 8080)
case "$published" in
    127.0.0.1:*)
        [[ "$published" != *$'\n'* ]] || \
            die "gateway has multiple published bindings: $published"
        printf 'gateway binding: %s\n' "$published"
        ;;
    *) die "gateway is not loopback-only: $published" ;;
esac

for service_port in 'db 5432' 'api 8000'; do
    read -r service port <<<"$service_port"
    published=$(compose_service_published_bindings "$current_env" "$service" "$port")
    [[ -z "$published" ]] || \
        die "LAGGENTE $service unexpectedly publishes container port $port: $published"
done

latest_backup=$(compose_with_release "$current_env" exec -T backup /opt/backup/backup.sh latest)
[[ "$latest_backup" =~ ^20[0-9]{6}T[0-9]{6}Z$ ]] || die "backup container returned an invalid latest backup id"
compose_with_release "$current_env" exec -T backup \
    /opt/backup/backup.sh verify "$latest_backup"
printf 'latest backup: %s (checksums and archive policy valid)\n' "$latest_backup"

curl --fail --silent --show-error --header 'Host: laggente.com' \
    "http://127.0.0.1:$laggente_loopback_port/api/health" >/dev/null
curl --fail --silent --show-error --header 'Host: laggente.com' \
    "http://127.0.0.1:$laggente_loopback_port/api/readyz" >/dev/null
printf 'loopback gateway health/readiness: healthy\n'

for public_check in \
    'https://laggente.com/ 200' \
    'https://app.laggente.com/ 308' \
    'https://mauro.laggente.com/ 200'; do
    read -r url expected_status <<<"$public_check"
    status=$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --max-time 15 "$url")
    printf '%s -> %s\n' "$url" "$status"
    [[ "$status" == "$expected_status" ]] || \
        die "public endpoint returned $status, expected $expected_status: $url"
done

if command -v openssl >/dev/null 2>&1; then
    expiry=$(echo | openssl s_client -servername laggente.com -connect laggente.com:443 2>/dev/null | \
        openssl x509 -noout -enddate)
    printf 'TLS %s\n' "$expiry"
fi
