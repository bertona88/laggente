#!/usr/bin/env bash
set -Eeuo pipefail

base_url=${LAGGENTE_BASE_URL:-https://laggente.com}
app_url=${LAGGENTE_APP_URL:-https://app.laggente.com}
pilot_url=${LAGGENTE_PILOT_URL:-https://mauro.laggente.com}

require_status() {
    local url=$1
    local expected_pattern=$2
    local status
    status=$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --max-time 15 "$url")
    if [[ ! "$status" =~ $expected_pattern ]]; then
        printf 'smoke: %s returned %s\n' "$url" "$status" >&2
        exit 1
    fi
    printf 'smoke: %s -> %s\n' "$url" "$status"
}

require_redirect() {
    local url=$1
    local expected_location=$2
    local headers
    local status
    local location
    headers=$(curl --silent --show-error --dump-header - --output /dev/null --max-time 15 "$url")
    status=$(awk '/^HTTP\// { value = $2 } END { print value }' <<<"$headers")
    location=$(awk '
        tolower($1) == "location:" {
            sub(/^[^:]+:[[:space:]]*/, "")
            sub(/\r$/, "")
            print
            exit
        }
    ' <<<"$headers")
    if [[ "$status" != 308 || "$location" != "$expected_location" ]]; then
        printf 'smoke: %s returned %s Location %s; expected 308 Location %s\n' \
            "$url" "${status:-unknown}" "${location:-<none>}" "$expected_location" >&2
        exit 1
    fi
    printf 'smoke: %s -> 308 %s\n' "$url" "$location"
}

require_status "$base_url/" '^200$'
require_redirect "$app_url/?source=smoke" "${app_url%/}/studio?source=smoke"
require_status "$pilot_url/" '^200$'
require_status "$base_url/api/health" '^200$'
require_status "$base_url/api/readyz" '^200$'
require_status "$base_url/api/v1" '^404$'
require_status "$base_url/api/this-route-must-not-be-spa" '^404$'

www_headers=$(curl --silent --show-error --head --max-time 15 https://www.laggente.com/)
if ! grep -Eqi '^location: https://laggente\.com/' <<<"$www_headers"; then
    printf 'smoke: www does not redirect to canonical apex\n' >&2
    exit 1
fi

security_headers=$(curl --silent --show-error --head --max-time 15 "$base_url/")
for header in strict-transport-security x-content-type-options referrer-policy permissions-policy content-security-policy; do
    if ! grep -Eqi "^$header:" <<<"$security_headers"; then
        printf 'smoke: missing security header %s\n' "$header" >&2
        exit 1
    fi
done
if grep -Eqi '^x-robots-tag:' <<<"$security_headers"; then
    printf 'smoke: canonical apex homepage unexpectedly has an X-Robots-Tag\n' >&2
    exit 1
fi

non_index_headers=$(curl --silent --show-error --head --max-time 15 \
    "$base_url/privacy/not-an-index-route")
pilot_headers=$(curl --silent --show-error --head --max-time 15 "$pilot_url/")
for protected_headers in "$non_index_headers" "$pilot_headers"; do
    if ! grep -Eqi '^x-robots-tag:[[:space:]]*noindex,[[:space:]]*nofollow' \
        <<<"$protected_headers"; then
        printf 'smoke: a non-indexable SPA surface is missing X-Robots-Tag\n' >&2
        exit 1
    fi
done

robots_body=$(curl --fail --silent --show-error --max-time 15 "$base_url/robots.txt")
sitemap_body=$(curl --fail --silent --show-error --max-time 15 "$base_url/sitemap.xml")
if ! grep -Fq 'Sitemap: https://laggente.com/sitemap.xml' <<<"$robots_body" || \
    ! grep -Fq '<loc>https://laggente.com/</loc>' <<<"$sitemap_body"; then
    printf 'smoke: crawler assets do not expose the canonical apex-only policy\n' >&2
    exit 1
fi

pilot_shell=$(curl --fail --silent --show-error --max-time 15 "$pilot_url/")
if ! grep -Fq 'id="root"' <<<"$pilot_shell"; then
    printf 'smoke: pilot host did not serve the Vite application shell\n' >&2
    exit 1
fi
module_path=$(sed -nE 's@.*src="(/assets/[^" ]+[.]js)".*@\1@p' <<<"$pilot_shell" | sed -n '1p')
if [[ -z "$module_path" ]]; then
    printf 'smoke: Vite application shell has no fingerprinted module asset\n' >&2
    exit 1
fi
curl --fail --silent --show-error --max-time 15 \
    "${pilot_url%/}$module_path" >/dev/null
printf 'smoke: Vite shell and module asset are reachable\n'

public_space=$(curl --fail --silent --show-error --max-time 15 \
    "${pilot_url%/}/api/v1/public/resolve")
if ! grep -Eq '"slug"[[:space:]]*:[[:space:]]*"mauro"' <<<"$public_space" || \
    ! grep -Eqi '"ai_label"[[:space:]]*:[[:space:]]*"[^"]*assistente AI' <<<"$public_space"; then
    printf 'smoke: Mauro public-space API metadata is missing its slug or AI-label contract\n' >&2
    exit 1
fi
printf 'smoke: Mauro public-space API metadata includes the AI-label contract\n'

printf 'smoke: production static-shell and API checks passed; visible disclosure remains a browser acceptance check\n'
