#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "$script_dir/.." && pwd)
acme_dns_version=2.0.2
acme_dns_archive="acme-dns_${acme_dns_version}_linux_amd64.tar.gz"
acme_dns_url="https://github.com/acme-dns/acme-dns/releases/download/v${acme_dns_version}/${acme_dns_archive}"
acme_dns_sha256=ff7aa309fb916012fc08dc7bd992c329b3930705ecb04161e57a5d910e80e9f0
credentials_path=/etc/letsencrypt/laggente-acme-dns.json
config_path=/etc/acme-dns/config.cfg
registration_backup=/var/backups/laggente-acme-dns/registration.db

if ((EUID != 0)); then
    printf 'run this installer as root\n' >&2
    exit 1
fi
if [[ $(uname -m) != x86_64 ]]; then
    printf 'the pinned acme-dns artifact supports x86_64 only\n' >&2
    exit 1
fi
for command in curl dig install jq sha256sum systemctl tar; do
    command -v "$command" >/dev/null 2>&1 || {
        printf 'missing required command: %s\n' "$command" >&2
        exit 1
    }
done

install_tmp=$(mktemp -d)
registration_tmp=
cleanup() {
    rm -rf -- "$install_tmp"
    if [[ -n "$registration_tmp" ]]; then
        rm -f -- "$registration_tmp"
    fi
}
trap cleanup EXIT HUP INT TERM

curl --fail --silent --show-error --location \
    --output "$install_tmp/$acme_dns_archive" "$acme_dns_url"
printf '%s  %s\n' "$acme_dns_sha256" "$install_tmp/$acme_dns_archive" | sha256sum --check --status
tar -xzf "$install_tmp/$acme_dns_archive" -C "$install_tmp" acme-dns LICENSE

if ! id acme_dns >/dev/null 2>&1; then
    useradd --system --home-dir /var/lib/acme-dns --shell /usr/sbin/nologin acme_dns
fi
install -d -m 0755 -o root -g root /etc/acme-dns /usr/local/libexec
install -d -m 0750 -o acme_dns -g acme_dns /var/lib/acme-dns
install -d -m 0700 -o root -g root /var/backups/laggente-acme-dns
install -m 0755 -o root -g root "$install_tmp/acme-dns" /usr/local/bin/acme-dns
install -m 0644 -o root -g root "$install_tmp/LICENSE" /usr/share/doc/acme-dns-LICENSE
install -m 0640 -o root -g acme_dns \
    "$repo_root/infra/acme-dns/config.cfg" "$config_path"
install -m 0644 -o root -g root \
    "$repo_root/infra/acme-dns/acme-dns.service" /etc/systemd/system/acme-dns.service
install -m 0755 -o root -g root \
    "$repo_root/infra/acme-dns/laggente-acme-dns-auth.py" \
    /usr/local/libexec/laggente-acme-dns-auth
install -m 0755 -o root -g root \
    "$repo_root/infra/acme-dns/laggente-certbot-deploy-hook.sh" \
    /usr/local/libexec/laggente-certbot-deploy-hook

systemctl daemon-reload

if [[ ! -s "$credentials_path" ]]; then
    registration_config="$install_tmp/config-registration.cfg"
    sed 's/^disable_registration = true$/disable_registration = false/' \
        "$repo_root/infra/acme-dns/config.cfg" >"$registration_config"
    install -m 0640 -o root -g acme_dns "$registration_config" "$config_path"
    systemctl enable --now acme-dns.service

    for _ in {1..20}; do
        if curl --fail --silent --show-error --max-time 2 \
            http://127.0.0.1:5399/health >/dev/null; then
            break
        fi
        sleep 0.5
    done
    curl --fail --silent --show-error \
        --header 'Content-Type: application/json' \
        --data '{"allowfrom":["127.0.0.1/32"]}' \
        --output "$install_tmp/registration.json" \
        http://127.0.0.1:5399/register
    jq -e '
        (.username | type == "string" and length > 0) and
        (.password | type == "string" and length > 0) and
        (.subdomain | type == "string" and length > 0) and
        (.fulldomain | type == "string" and endswith(".auth.laggente.com"))
    ' "$install_tmp/registration.json" >/dev/null
    registration_tmp=$(mktemp)
    chmod 0600 "$registration_tmp"
    jq '. + {api_url:"http://127.0.0.1:5399/update"}' \
        "$install_tmp/registration.json" >"$registration_tmp"
    install -m 0600 -o root -g root "$registration_tmp" "$credentials_path"
fi

# Registration is needed only once. Reinstall the production configuration and
# prove that the public API surface is closed before leaving the service enabled.
install -m 0640 -o root -g acme_dns \
    "$repo_root/infra/acme-dns/config.cfg" "$config_path"
systemctl enable acme-dns.service
systemctl restart acme-dns.service
curl --fail --silent --show-error --max-time 5 \
    http://127.0.0.1:5399/health >/dev/null
registration_status=$(curl --silent --output /dev/null --write-out '%{http_code}' \
    --header 'Content-Type: application/json' --data '{}' \
    http://127.0.0.1:5399/register)
if [[ "$registration_status" != 404 ]]; then
    printf 'acme-dns registration endpoint returned %s instead of 404\n' "$registration_status" >&2
    exit 1
fi

if [[ ! -s "$registration_backup" ]]; then
    systemctl stop acme-dns.service
    install -m 0600 -o root -g root \
        /var/lib/acme-dns/acme-dns.db "$registration_backup"
    systemctl start acme-dns.service
    curl --fail --silent --show-error --max-time 5 \
        http://127.0.0.1:5399/health >/dev/null
fi

fulldomain=$(jq -r '.fulldomain' "$credentials_path")
printf 'acme-dns is healthy; registration is closed.\n'
printf 'CNAME target for _acme-challenge.laggente.com: %s\n' "$fulldomain"
