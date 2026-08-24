#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=production-lib.sh
source "$script_dir/production-lib.sh"

configure_docker_client
require_repo
require_command jq
require_command dig
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

systemctl is-active --quiet acme-dns.service || die "acme-dns.service is not active"
systemctl is-active --quiet certbot.timer || die "certbot.timer is not active"
auth_ns=$(dig +short NS auth.laggente.com @1.1.1.1 | sed -n '1p')
auth_a=$(dig +short A auth.laggente.com @1.1.1.1 | sed -n '1p')
[[ ${auth_ns%.} == auth.laggente.com ]] || \
    die "public auth.laggente.com NS delegation is missing"
[[ "$auth_a" == 116.203.123.0 ]] || \
    die "public auth.laggente.com A does not resolve to the Hetzner server"
printf 'ACME DNS delegation/service and Certbot timer: healthy\n'

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
    certificate_text=$(openssl s_client \
        -servername tls-probe.laggente.com \
        -connect laggente.com:443 </dev/null 2>/dev/null | \
        openssl x509 -noout -enddate -ext subjectAltName)
    grep -Fq 'DNS:laggente.com' <<<"$certificate_text" || \
        die "active certificate is missing the laggente.com SAN"
    grep -Fq 'DNS:*.laggente.com' <<<"$certificate_text" || \
        die "active certificate is missing the *.laggente.com SAN"
    printf 'TLS wildcard lineage: valid for apex and professional subdomains\n'
    grep -F 'notAfter=' <<<"$certificate_text"
fi
