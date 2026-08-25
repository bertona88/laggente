#!/usr/bin/env bash
set -Eeuo pipefail

credentials_path=/etc/letsencrypt/laggente-acme-dns.json
cert_name=laggente-wildcard
expected_ip=116.203.123.0

if ((EUID != 0)); then
    printf 'run this script as root\n' >&2
    exit 1
fi
for command in certbot curl dig jq openssl systemctl; do
    command -v "$command" >/dev/null 2>&1 || {
        printf 'missing required command: %s\n' "$command" >&2
        exit 1
    }
done
if [[ ! -s "$credentials_path" ]]; then
    printf 'missing acme-dns credentials: %s\n' "$credentials_path" >&2
    exit 1
fi
if [[ $(stat -c '%U %a' "$credentials_path") != 'root 600' ]]; then
    printf 'acme-dns credentials must be root-owned mode 600\n' >&2
    exit 1
fi
systemctl is-active --quiet acme-dns.service || {
    printf 'acme-dns.service is not active\n' >&2
    exit 1
}
curl --fail --silent --show-error --max-time 5 \
    http://127.0.0.1:5399/health >/dev/null

fulldomain=$(jq -r '.fulldomain' "$credentials_path")
public_a=$(dig +short A auth.laggente.com @1.1.1.1 | sed -n '1p')
public_ns=$(dig +short NS auth.laggente.com @1.1.1.1 | sed -n '1p')
public_cname=$(dig +short CNAME _acme-challenge.laggente.com @1.1.1.1 | sed -n '1p')
if [[ "$public_a" != "$expected_ip" ]]; then
    printf 'auth.laggente.com A is %s, expected %s\n' "${public_a:-<missing>}" "$expected_ip" >&2
    exit 1
fi
if [[ ${public_ns%.} != auth.laggente.com ]]; then
    printf 'auth.laggente.com NS is %s, expected auth.laggente.com\n' "${public_ns:-<missing>}" >&2
    exit 1
fi
if [[ ${public_cname%.} != ${fulldomain%.} ]]; then
    printf '_acme-challenge CNAME is %s, expected %s\n' \
        "${public_cname:-<missing>}" "$fulldomain" >&2
    exit 1
fi

certbot certonly \
    --manual \
    --preferred-challenges dns \
    --manual-auth-hook /usr/local/libexec/laggente-acme-dns-auth \
    --deploy-hook /usr/local/libexec/laggente-certbot-deploy-hook \
    --non-interactive \
    --agree-tos \
    --cert-name "$cert_name" \
    --domains laggente.com \
    --domains '*.laggente.com'

certificate=/etc/letsencrypt/live/$cert_name/fullchain.pem
private_key=/etc/letsencrypt/live/$cert_name/privkey.pem
test -r "$certificate"
test -r "$private_key"
certificate_text=$(openssl x509 -in "$certificate" -noout -ext subjectAltName)
grep -Fq 'DNS:laggente.com' <<<"$certificate_text"
grep -Fq 'DNS:*.laggente.com' <<<"$certificate_text"

certbot renew --dry-run --cert-name "$cert_name"
printf 'wildcard certificate issued and dry-run renewal passed: %s\n' "$certificate"
