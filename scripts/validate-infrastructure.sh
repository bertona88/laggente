#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "$script_dir/.." && pwd)

bash -n "$repo_root"/scripts/*.sh
sh -n "$repo_root"/infra/backup/*.sh

bootstrap_script="$repo_root/scripts/bootstrap-server.sh"
if ! grep -Eq '^[[:space:]]+slirp4netns[[:space:]]*\\$' "$bootstrap_script"; then
    printf 'server bootstrap does not install the supported rootless network backend\n' >&2
    exit 1
fi
for rootless_contract in \
    'Environment="DOCKERD_ROOTLESS_ROOTLESSKIT_NET=slirp4netns"' \
    'Environment="DOCKERD_ROOTLESS_ROOTLESSKIT_PORT_DRIVER=builtin"' \
    'rootless_network_published=$(rootless_docker port'; do
    if ! grep -Fq "$rootless_contract" "$bootstrap_script"; then
        printf 'server bootstrap is missing rootless Docker contract: %s\n' \
            "$rootless_contract" >&2
        exit 1
    fi
done

[[ -f "$repo_root/infra/secrets/database.env.example" ]] || {
    printf 'missing database secret example\n' >&2
    exit 1
}
[[ -f "$repo_root/infra/secrets/application.env.example" ]] || {
    printf 'missing application secret example\n' >&2
    exit 1
}
for dockerignore_pattern in '**/.env' '**/.env.*'; do
    if ! grep -Fxq "$dockerignore_pattern" "$repo_root/.dockerignore"; then
        printf 'root Docker build context is missing recursive secret exclusion: %s\n' \
            "$dockerignore_pattern" >&2
        exit 1
    fi
done
if ! grep -Fq -- '--no-access-log' "$repo_root/services/api/Dockerfile"; then
    printf 'API runtime must disable query-bearing Uvicorn access logs\n' >&2
    exit 1
fi
if grep -q 'LAGGENTE_SECRETS_FILE\|production\.env' "$repo_root/compose.yaml"; then
    printf 'compose.yaml still references the legacy combined secret file\n' >&2
    exit 1
fi
if grep -Eq '^[[:space:]]{2}web:' "$repo_root/compose.yaml"; then
    printf 'compose.yaml still defines a separate web runtime instead of the static gateway\n' >&2
    exit 1
fi
if grep -Eq 'web:3000|NEXT_PUBLIC_|[.]next/cache' \
    "$repo_root/compose.yaml" "$repo_root/infra/gateway/nginx.conf"; then
    printf 'production infrastructure still references the removed Next.js runtime\n' >&2
    exit 1
fi
if ! grep -Fq "headers={'Host':'laggente.com'}" "$repo_root/compose.yaml"; then
    printf 'API healthcheck does not send an explicitly trusted production Host header\n' >&2
    exit 1
fi
if ! grep -Fq 'log_parameter_max_length=0' "$repo_root/compose.yaml"; then
    printf 'PostgreSQL slow-statement logging must not include private bind values\n' >&2
    exit 1
fi
if ! grep -Fq '      - FOWNER' "$repo_root/compose.yaml"; then
    printf 'data initializer cannot repair modes after ownership moves to runtime UID 10001\n' >&2
    exit 1
fi
if ! grep -Fq 'COPY --from=web-build /build/dist/' \
    "$repo_root/infra/gateway/Dockerfile"; then
    printf 'gateway image does not copy the built Vite assets into nginx\n' >&2
    exit 1
fi
if ! grep -Fq 'try_files $uri $uri/ /index.html;' \
    "$repo_root/infra/gateway/nginx.conf"; then
    printf 'gateway nginx is missing the SPA history fallback\n' >&2
    exit 1
fi
if ! grep -Fq 'location = /api/v1' "$repo_root/infra/gateway/nginx.conf" || \
    ! grep -Fq 'location ^~ /api/v1/' "$repo_root/infra/gateway/nginx.conf" || \
    ! grep -Fq 'proxy_pass http://$api_upstream;' "$repo_root/infra/gateway/nginx.conf"; then
    printf 'gateway nginx is missing the same-origin /api/v1 FastAPI proxy\n' >&2
    exit 1
fi
for nginx_file in \
    "$repo_root/infra/gateway/nginx.conf" \
    "$repo_root/infra/nginx/laggente.conf"; do
    if ! grep -Fq 'location = /api/v1' "$nginx_file" || \
        ! grep -Fq 'location /api/' "$nginx_file"; then
        printf '%s is missing the exact API root or unknown-API boundary\n' "$nginx_file" >&2
        exit 1
    fi
done
if grep -Eq '^[[:space:]]*location[[:space:]]+\^~[[:space:]]+/api/v1/[[:space:]]*\{' \
    "$repo_root/infra/nginx/laggente.conf"; then
    printf 'host nginx /api/v1 prefix would bypass the attachment regex limiter\n' >&2
    exit 1
fi
if [[ $(grep -Fc 'limit_req zone=laggente_api burst=5 nodelay;' \
    "$repo_root/infra/nginx/laggente.conf") -ne 3 ]]; then
    printf 'host nginx public health routes must each use the modest API rate limit\n' >&2
    exit 1
fi
if grep -Fq 'include /etc/nginx/proxy_params;' \
    "$repo_root/infra/nginx/laggente.conf"; then
    printf 'host nginx must not combine distribution proxy_params with its explicit proxy headers\n' >&2
    exit 1
fi
if ! grep -Fq 'Cross-Origin-Resource-Policy "same-origin"' \
    "$repo_root/infra/nginx/laggente.conf"; then
    printf 'host nginx must prevent sibling origins from embedding private media\n' >&2
    exit 1
fi
if ! grep -Fq 'return 308 $laggente_canonical_location$is_args$args;' \
    "$repo_root/infra/gateway/nginx.conf"; then
    printf 'gateway nginx is missing query-preserving canonical product redirects\n' >&2
    exit 1
fi
if grep -Eq '^[[:space:]]*~[^";]*[{][0-9,]+[}]' \
    "$repo_root/infra/gateway/nginx.conf"; then
    printf 'gateway nginx contains an unquoted regex with brace quantifiers\n' >&2
    exit 1
fi
if [[ $(grep -Ec '^[[:space:]]*"~.*[{]0,61[}].*"' \
    "$repo_root/infra/gateway/nginx.conf") -ne 3 ]]; then
    printf 'gateway nginx brace-quantified map regexes are not safely quoted\n' >&2
    exit 1
fi
if grep -q '/api/v1/uploads/' "$repo_root/infra/nginx/laggente.conf"; then
    printf 'host nginx still contains the obsolete upload route\n' >&2
    exit 1
fi
if ! grep -Eq 'location ~ \^/api/v1/public/conversations/\[\^/\]\+/attachments/\?\$' \
    "$repo_root/infra/nginx/laggente.conf"; then
    printf 'host nginx is missing the public-conversation attachment limiter\n' >&2
    exit 1
fi
if ! grep -Fq 'limit_conn laggente_upload_connections 2;' \
    "$repo_root/infra/nginx/laggente.conf" || \
   ! grep -Fq 'MAX_CONCURRENT_UPLOAD_REQUESTS = 2' "$repo_root/services/api/app/main.py"; then
    printf 'public multipart concurrency is not bounded consistently at edge and API\n' >&2
    exit 1
fi

assert_token_safe_access_log() {
    local nginx_file=$1
    local format
    format=$(awk '
        /log_format[[:space:]]+laggente_safe[[:space:]]+escape=json/ { capture = 1 }
        capture { print }
        capture && /;/ { exit }
    ' "$nginx_file")
    [[ -n "$format" ]] || {
        printf '%s is missing the token-safe access-log format\n' "$nginx_file" >&2
        exit 1
    }
    if printf '%s\n' "$format" | grep -Eq \
        '[$]request([^_[:alnum:]]|$)|[$](request_uri|args|is_args|query_string|http_referer)([^_[:alnum:]]|$)'; then
        printf '%s token-safe access-log format includes URL args, referer, or the raw request\n' "$nginx_file" >&2
        exit 1
    fi
    for required_variable in '$request_method' '$uri' '$server_protocol' '$status' '$request_time' '$request_id'; do
        if ! printf '%s\n' "$format" | grep -Fq "$required_variable"; then
            printf '%s token-safe access-log format is missing %s\n' \
                "$nginx_file" "$required_variable" >&2
            exit 1
        fi
    done
    if ! grep -Eq 'access_log[[:space:]]+[^;]+[[:space:]]+laggente_safe;' "$nginx_file"; then
        printf '%s does not activate the token-safe access-log format\n' "$nginx_file" >&2
        exit 1
    fi
}

assert_token_safe_access_log "$repo_root/infra/gateway/nginx.conf"
assert_token_safe_access_log "$repo_root/infra/nginx/laggente.conf"
if ! grep -Eq '^error_log[[:space:]]+/dev/stderr[[:space:]]+crit;' \
    "$repo_root/infra/gateway/nginx.conf"; then
    printf 'gateway error logging is verbose enough to expose query-bearing request lines\n' >&2
    exit 1
fi
if [[ $(grep -Ec '^[[:space:]]*error_log[[:space:]]+/var/log/nginx/laggente[.]error[.]log[[:space:]]+crit;' \
    "$repo_root/infra/nginx/laggente.conf") -ne 3 ]]; then
    printf 'each host nginx server must suppress request-context error logging below crit\n' >&2
    exit 1
fi

validation_tmp=$(mktemp -d)
gateway_validation_container=
cleanup() {
    if [[ -n "$gateway_validation_container" ]] && command -v docker >/dev/null 2>&1; then
        docker rm -f "$gateway_validation_container" >/dev/null 2>&1 || true
    fi
    rm -rf -- "$validation_tmp"
}
trap cleanup EXIT HUP INT TERM

existing_release_env="$validation_tmp/existing-release.env"
dangling_release_env="$validation_tmp/dangling-release.env"
printf 'immutable release metadata\n' >"$existing_release_env"
ln -s "$validation_tmp/missing-release-target" "$dangling_release_env"
for reused_release_path in "$existing_release_env" "$dangling_release_env"; do
    if (
        # shellcheck source=production-lib.sh
        source "$repo_root/scripts/production-lib.sh"
        require_unused_release_path "$reused_release_path"
    ) >"$validation_tmp/reused-release.log" 2>&1; then
        printf 'existing release metadata path was accepted for reuse: %s\n' \
            "$reused_release_path" >&2
        exit 1
    fi
done
if ! grep -Fq 'release metadata already exists and is immutable' \
    "$validation_tmp/reused-release.log"; then
    printf 'release metadata reuse refusal was not reported clearly\n' >&2
    exit 1
fi
for reserved_release_id in current previous; do
    if (
        # shellcheck source=production-lib.sh
        source "$repo_root/scripts/production-lib.sh"
        validate_release_id "$reserved_release_id"
    ) >"$validation_tmp/reserved-release.log" 2>&1; then
        printf 'reserved release pointer name was accepted as a release id: %s\n' \
            "$reserved_release_id" >&2
        exit 1
    fi
done
if ! grep -Fq 'release id is reserved for release pointers' \
    "$validation_tmp/reserved-release.log"; then
    printf 'reserved release-id refusal was not reported clearly\n' >&2
    exit 1
fi

archive_test_uploads="$validation_tmp/uploads"
archive_test_output="$validation_tmp/uploads.tar.gz"
mkdir -p "$archive_test_uploads/account/conversation" \
    "$archive_test_uploads/account/tmp" \
    "$archive_test_uploads/account/.transcription-tmp"
printf 'image' >"$archive_test_uploads/account/conversation/photo.jpg"
printf 'image' >"$archive_test_uploads/account/conversation/planimetria.PNG"
printf 'audio' >"$archive_test_uploads/account/conversation/voice.wav"
printf 'audio' >"$archive_test_uploads/account/conversation/VOICE.MP3"
printf 'temporary image' >"$archive_test_uploads/account/tmp/not-durable.jpg"
printf 'temporary audio' >"$archive_test_uploads/account/.transcription-tmp/raw.m4a"
sh "$repo_root/infra/backup/archive-uploads.sh" create \
    "$archive_test_uploads" "$archive_test_output"
archive_listing=$(tar -tzf "$archive_test_output")
printf '%s\n' "$archive_listing" | grep -q 'account/conversation/photo.jpg'
printf '%s\n' "$archive_listing" | grep -q 'account/conversation/planimetria.PNG'
if printf '%s\n' "$archive_listing" | grep -Eqi \
    '[.](mp3|wav|webm|ogg|oga|opus|m4a|mp4|aac|flac|amr|aiff|aif|caf|mpeg|mpga)$|/(tmp|[.]transcription-tmp)/'; then
    printf 'upload archive contains raw audio or temporary content\n' >&2
    exit 1
fi

corrupt_archive="$validation_tmp/corrupt-uploads.tar.gz"
printf 'not a gzip archive\n' >"$corrupt_archive"
if sh "$repo_root/infra/backup/archive-uploads.sh" verify "$corrupt_archive" \
    >"$validation_tmp/corrupt-archive.log" 2>&1; then
    printf 'corrupt upload archive unexpectedly passed verification\n' >&2
    exit 1
fi
if ! grep -Fq 'upload archive is unreadable or corrupt' \
    "$validation_tmp/corrupt-archive.log"; then
    printf 'corrupt upload archive failure was not reported explicitly\n' >&2
    exit 1
fi

if grep -Fq 'wait_for_gateway ||' \
    "$repo_root/scripts/deploy-production.sh" \
    "$repo_root/scripts/rollback-production.sh"; then
    printf 'gateway health failure still bypasses explicit application recovery\n' >&2
    exit 1
fi
grep -Fq 'rollback_application 1' "$repo_root/scripts/deploy-production.sh" || {
    printf 'deployment health failure does not explicitly restore the previous application\n' >&2
    exit 1
}
grep -Fq 'restore_current 1' "$repo_root/scripts/rollback-production.sh" || {
    printf 'rollback health failure does not explicitly restore the current application\n' >&2
    exit 1
}
for signal_status in 129 130 143; do
    grep -Fq "rollback_application $signal_status" \
        "$repo_root/scripts/deploy-production.sh" || {
        printf 'deployment activation does not recover on signal status %s\n' \
            "$signal_status" >&2
        exit 1
    }
    grep -Fq "restore_current $signal_status" \
        "$repo_root/scripts/rollback-production.sh" || {
        printf 'application rollback does not restore on signal status %s\n' \
            "$signal_status" >&2
        exit 1
    }
done
if [[ $(grep -Fxc '    trap - ERR HUP INT TERM' \
    "$repo_root/scripts/deploy-production.sh") -ne 1 ]] || \
   [[ $(grep -Fxc '    trap - ERR HUP INT TERM' \
    "$repo_root/scripts/rollback-production.sh") -ne 1 ]]; then
    printf 'activation recovery handlers do not disarm recursive signal/error traps\n' >&2
    exit 1
fi
grep -Fq 'trap - ERR HUP INT TERM' "$repo_root/scripts/deploy-production.sh" || exit 1
grep -Fq 'trap - ERR HUP INT TERM' "$repo_root/scripts/rollback-production.sh" || exit 1
if grep -Eq 'pull[[:space:]]+(db|data-init)|pull[[:space:]]+db[[:space:]]+data-init' \
    "$repo_root/scripts/deploy-production.sh"; then
    printf 'application deploy still upgrades mutable foundation images as a side effect\n' >&2
    exit 1
fi

# A daemon invokes run_backup as an `if` condition. POSIX shells can suppress `set -e` in that
# context, so inject a pg_dump failure that leaves a file behind and prove it still cannot be
# validated, published, or recorded as successful. The fake sleep stops the retry loop after the
# first attempt without weakening the production retry behavior.
backup_failure_bin="$validation_tmp/backup-failure-bin"
backup_failure_root="$validation_tmp/backup-failure-root"
backup_failure_uploads="$validation_tmp/backup-failure-uploads"
mkdir -p "$backup_failure_bin" "$backup_failure_root" "$backup_failure_uploads"
printf '%s\n' \
    '#!/bin/sh' \
    'exit 0' \
    >"$backup_failure_bin/flock"
printf '%s\n' \
    '#!/bin/sh' \
    'output=' \
    'for argument do' \
    '    case "$argument" in --file=*) output=${argument#--file=} ;; esac' \
    'done' \
    '[ -n "$output" ] || exit 64' \
    'printf "%s\\n" "deliberately incomplete database dump" >"$output"' \
    'exit 42' \
    >"$backup_failure_bin/pg_dump"
printf '%s\n' \
    '#!/bin/sh' \
    'exit 0' \
    >"$backup_failure_bin/pg_restore"
printf '%s\n' \
    '#!/bin/sh' \
    'exit 99' \
    >"$backup_failure_bin/sleep"
chmod 0700 \
    "$backup_failure_bin/flock" \
    "$backup_failure_bin/pg_dump" \
    "$backup_failure_bin/pg_restore" \
    "$backup_failure_bin/sleep"

set +e
PATH="$backup_failure_bin:$PATH" \
BACKUP_ROOT="$backup_failure_root" \
UPLOADS_ROOT="$backup_failure_uploads" \
ARCHIVE_HELPER="$repo_root/infra/backup/archive-uploads.sh" \
POSTGRES_USER=validation \
POSTGRES_PASSWORD=validation \
POSTGRES_DB=validation \
BACKUP_RETRY_SECONDS=60 \
sh "$repo_root/infra/backup/backup.sh" daemon \
    >"$validation_tmp/backup-failure.log" 2>&1
backup_failure_status=$?
set -e
if [[ $backup_failure_status -eq 0 ]]; then
    printf 'backup failure injection unexpectedly returned success\n' >&2
    exit 1
fi
if find "$backup_failure_root" -mindepth 1 -maxdepth 1 -type d \
    \( -name '20??????T??????Z' -o -name '.partial-*' \) | grep -q .; then
    printf 'failed backup published or retained a partial backup set\n' >&2
    exit 1
fi
if [[ -e "$backup_failure_root/.last_success_epoch" ]]; then
    printf 'failed backup published a success marker\n' >&2
    exit 1
fi
if ! grep -Fq 'backup: database snapshot failed' "$validation_tmp/backup-failure.log"; then
    printf 'failed backup did not report its critical capture failure\n' >&2
    exit 1
fi
if grep -q 'find .*data/backups' \
    "$repo_root/scripts/audit-production.sh" \
    "$repo_root/scripts/verify-backup-restore.sh"; then
    printf 'host-side backup inspection is unsafe with rootless UID mapping\n' >&2
    exit 1
fi

combined_env="$validation_tmp/combined.env"
printf '%s\n' \
    'POSTGRES_USER=laggente' \
    'POSTGRES_DB=laggente' \
    'POSTGRES_PASSWORD=validation-database-password' \
    'DATABASE_URL=postgresql+psycopg://laggente:validation-database-password@db:5432/laggente' \
    'APP_ENV=development' \
    'SESSION_SECRET=validation-session-secret-which-is-not-used' \
    'BASE_DOMAIN=unsafe.example' \
    'APP_ORIGIN=http://mauro.laggente.com/' \
    'CORS_ORIGINS=https://laggente.com,https://app.laggente.com,https://mauro.laggente.com' \
    'TRUSTED_HOSTS=*' \
    'COOKIE_SECURE=false' \
    'AUTH_MODE=pilot_password' \
    'PILOT_EMAIL=validation@example.invalid' \
    'PILOT_PASSWORD=validation-pilot-password' \
    'PILOT_NAME=Mauro Rossi' \
    'SEED_DEMO=true' \
    'AUTO_CREATE_SCHEMA=true' \
    'OPENAI_API_KEY=validation-openai-key' \
    'OPENAI_MODEL=gpt-5.6' \
    'RESEND_API_KEY=' \
    'FROM_EMAIL=' \
    'UPLOAD_DIR=/data/uploads' \
    'MAX_UPLOAD_BYTES=10485760' \
    >"$combined_env"

database_env="$validation_tmp/database.env"
application_env="$validation_tmp/application.env"
bash "$repo_root/scripts/generate-production-env.sh" \
    --source-env "$combined_env" \
    --database-output "$database_env" \
    --application-output "$application_env" \
    >/dev/null

file_mode() {
    stat -c '%a' "$1" 2>/dev/null || stat -f '%Lp' "$1"
}
[[ $(file_mode "$database_env") == 600 ]] || {
    printf 'generated database env does not have mode 0600\n' >&2
    exit 1
}
[[ $(file_mode "$application_env") == 600 ]] || {
    printf 'generated application env does not have mode 0600\n' >&2
    exit 1
}
grep -q '^POSTGRES_PASSWORD=' "$database_env"
grep -q '^OPENAI_API_KEY=' "$application_env"
for production_line in \
    'APP_ENV=production' \
    'BASE_DOMAIN=laggente.com' \
    'APP_ORIGIN=https://app.laggente.com' \
    'CORS_ORIGINS=https://app.laggente.com' \
    'TRUSTED_HOSTS=laggente.com,*.laggente.com' \
    'COOKIE_SECURE=true' \
    'AUTO_CREATE_SCHEMA=false'; do
    grep -Fxq "$production_line" "$application_env" || {
        printf 'generated application env did not normalize %s\n' "$production_line" >&2
        exit 1
    }
done
grep -q '^CONVERSATION_RETENTION_DAYS=365$' "$application_env"
grep -q '^PRIVACY_NOTICE_VERSION=2026-08-22$' "$application_env"
(
    # Exercise the same exact production-origin/host contract used by deploy and audit.
    # shellcheck source=production-lib.sh
    source "$repo_root/scripts/production-lib.sh"
    require_production_application_contract "$application_env" validation-application
)
unsafe_application_env="$validation_tmp/unsafe-application.env"
awk '
    /^APP_ORIGIN=/ { print "APP_ORIGIN=http://mauro.laggente.com"; next }
    { print }
' "$application_env" >"$unsafe_application_env"
if (
    # shellcheck source=production-lib.sh
    source "$repo_root/scripts/production-lib.sh"
    require_production_application_contract \
        "$unsafe_application_env" validation-unsafe-application
) >/dev/null 2>&1; then
    printf 'production application contract accepted an unsafe APP_ORIGIN\n' >&2
    exit 1
fi
if grep -Eq '^(OPENAI_API_KEY|SESSION_SECRET|PILOT_PASSWORD|RESEND_API_KEY)=' "$database_env"; then
    printf 'generated database env crossed the application-secret boundary\n' >&2
    exit 1
fi
if grep -Eq '^(POSTGRES_USER|POSTGRES_DB|POSTGRES_PASSWORD|DATABASE_URL)=' "$application_env"; then
    printf 'generated application env crossed the database-secret boundary\n' >&2
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    printf 'static shell and secret-boundary validation passed; Docker is unavailable, so Compose/build validation was skipped\n'
    exit 0
fi

docker_security_options=$(docker info --format '{{json .SecurityOptions}}')
if [[ "$docker_security_options" == *'name=rootless'* ]]; then
    command -v slirp4netns >/dev/null 2>&1 || {
        printf 'rootless Docker is running without the required slirp4netns backend\n' >&2
        exit 1
    }
    if ! ps -u "$(id -u)" -o args= | \
        grep -F 'rootlesskit ' | \
        grep -F -- '--net=slirp4netns' | \
        grep -F -- '--port-driver=builtin' >/dev/null; then
        printf 'rootless Docker is not using slirp4netns with the builtin port driver\n' >&2
        exit 1
    fi
fi

command -v jq >/dev/null 2>&1 || {
    printf 'jq is required for Compose secret-boundary validation\n' >&2
    exit 1
}

# An exposed container port is internal metadata, not a host publication. Docker
# represents that state as null; retain a regression fixture because `compose
# port` has reported the exposed value itself in deployed Compose versions.
unpublished_binding=$(
    printf '%s\n' \
        '[{"Config":{"ExposedPorts":{"5432/tcp":{}}},"NetworkSettings":{"Ports":{"5432/tcp":null}}}]' | (
        # shellcheck source=production-lib.sh
        source "$repo_root/scripts/production-lib.sh"
        inspect_published_port_bindings 5432
    )
)
[[ -z "$unpublished_binding" ]] || {
    printf 'exposed-only container port was misclassified as host-published: %s\n' \
        "$unpublished_binding" >&2
    exit 1
}
published_binding=$(
    printf '%s\n' \
        '[{"NetworkSettings":{"Ports":{"8080/tcp":[{"HostIp":"127.0.0.1","HostPort":"45200"}]}}}]' | (
        # shellcheck source=production-lib.sh
        source "$repo_root/scripts/production-lib.sh"
        inspect_published_port_bindings 8080
    )
)
[[ "$published_binding" == '127.0.0.1:45200' ]] || {
    printf 'published container port binding was not extracted correctly: %s\n' \
        "${published_binding:-<none>}" >&2
    exit 1
}
grep -Fq 'compose_service_published_bindings' \
    "$repo_root/scripts/audit-production.sh" || {
    printf 'production audit does not inspect actual Docker host bindings\n' >&2
    exit 1
}

release_env="$validation_tmp/release.env"
printf '%s\n' \
    'LAGGENTE_RELEASE=validation' \
    'LAGGENTE_GIT_SHA=0000000000000000000000000000000000000000' \
    "LAGGENTE_DATABASE_ENV_FILE=$database_env" \
    "LAGGENTE_APPLICATION_ENV_FILE=$application_env" \
    'LAGGENTE_DATA_ROOT=/opt/laggente/data' \
    >"$release_env"

docker compose \
    --project-directory "$repo_root" \
    --file "$repo_root/compose.yaml" \
    --env-file "$release_env" \
    config --quiet

compose_json="$validation_tmp/compose.json"
docker compose \
    --project-directory "$repo_root" \
    --file "$repo_root/compose.yaml" \
    --env-file "$release_env" \
    config --format json \
    >"$compose_json"

if ! jq -e '
    .services as $services
    | (["db", "migrate", "backup"] | all(.[];
        ($services[.].environment.POSTGRES_PASSWORD != null)
        and ($services[.].environment.OPENAI_API_KEY == null)
        and ($services[.].environment.SESSION_SECRET == null)
        and ($services[.].environment.PILOT_PASSWORD == null)
        and ($services[.].environment.RESEND_API_KEY == null)))
    and ($services.api.environment.POSTGRES_PASSWORD != null)
    and ($services.api.environment.OPENAI_API_KEY != null)
    and ($services.api.environment.SESSION_SECRET != null)
    and ($services.web == null)
    and ($services.gateway.environment.POSTGRES_PASSWORD == null)
    and ($services.gateway.environment.DATABASE_URL == null)
    and ($services.gateway.environment.OPENAI_API_KEY == null)
    and ($services.gateway.environment.SESSION_SECRET == null)
    and ($services.gateway.environment.PILOT_PASSWORD == null)
    and ($services.gateway.environment.RESEND_API_KEY == null)
    and (($services.migrate.volumes // []) | length == 0)
' "$compose_json" >/dev/null; then
    printf 'resolved Compose configuration violates the service secret boundary\n' >&2
    exit 1
fi

if [[ ${1:-} == --build ]]; then
    command -v curl >/dev/null 2>&1 || {
        printf 'curl is required for built gateway validation\n' >&2
        exit 1
    }
    export COMPOSE_PARALLEL_LIMIT=1
    docker compose \
        --project-directory "$repo_root" \
        --file "$repo_root/compose.yaml" \
        --env-file "$release_env" \
        build gateway backup

    gateway_validation_image=$(jq -r '.services.gateway.image' "$compose_json")
    [[ -n "$gateway_validation_image" && "$gateway_validation_image" != null ]] || {
        printf 'resolved Compose gateway image is missing\n' >&2
        exit 1
    }
    gateway_validation_container="laggente-gateway-validation-$$"
    gateway_validation_started=false
    gateway_run_log="$validation_tmp/gateway-run.log"
    # Bind an explicit high loopback port so the exact mapping can be inspect-enforced.
    # Mirror the Compose runtime's read-only filesystem and writable nginx tmpfs mounts;
    # otherwise the non-root nginx process exits before Docker retains a useful mapping.
    # A collision is harmless: choose another candidate without widening to 0.0.0.0.
    for _attempt in {1..12}; do
        gateway_validation_port=$((49152 + ((RANDOM * 32768 + RANDOM + $$) % 16384)))
        if docker run --detach --rm \
            --name "$gateway_validation_container" \
            --publish "127.0.0.1:${gateway_validation_port}:8080" \
            --read-only \
            --cap-drop ALL \
            --tmpfs /tmp:size=32m,mode=1777 \
            --tmpfs /var/cache/nginx:size=32m,mode=0755 \
            "$gateway_validation_image" \
            >"$validation_tmp/gateway-container-id" 2>"$gateway_run_log"; then
            gateway_validation_started=true
            break
        fi
        docker rm -f "$gateway_validation_container" >/dev/null 2>&1 || true
    done
    [[ "$gateway_validation_started" == true ]] || {
        printf 'could not start the built gateway on an ephemeral loopback port\n' >&2
        sed -n '1,20p' "$gateway_run_log" >&2
        exit 1
    }

    if ! gateway_published=$(docker inspect "$gateway_validation_container" | jq -er '
        .[0].NetworkSettings.Ports["8080/tcp"] as $bindings
        | select(($bindings | type) == "array" and ($bindings | length) == 1)
        | $bindings[0]
        | select(.HostIp == "127.0.0.1")
        | .HostPort
    '); then
        printf 'built gateway validation port is not published loopback-only\n' >&2
        exit 1
    fi
    [[ "$gateway_published" == "$gateway_validation_port" ]] || {
        printf 'built gateway validation port resolved to %s, expected %s\n' \
            "$gateway_published" "$gateway_validation_port" >&2
        exit 1
    }
    gateway_validation_url="http://127.0.0.1:$gateway_validation_port"

    gateway_ready=false
    for _attempt in {1..20}; do
        if curl --fail --silent --show-error \
            --header 'Host: laggente.com' \
            "$gateway_validation_url/_gateway_health" >/dev/null; then
            gateway_ready=true
            break
        fi
        sleep 0.25
    done
    [[ "$gateway_ready" == true ]] || {
        printf 'built gateway did not serve its static health target\n' >&2
        exit 1
    }

    require_gateway_status() {
        local host=$1
        local path=$2
        local expected=$3
        local actual
        actual=$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
            --header "Host: $host" "$gateway_validation_url$path")
        [[ "$actual" == "$expected" ]] || {
            printf 'built gateway %s%s returned %s, expected %s\n' \
                "$host" "$path" "$actual" "$expected" >&2
            exit 1
        }
    }

    require_gateway_location() {
        local host=$1
        local path=$2
        local expected=$3
        local headers
        local actual
        headers=$(curl --silent --show-error --dump-header - --output /dev/null \
            --header "Host: $host" "$gateway_validation_url$path")
        actual=$(printf '%s\n' "$headers" | awk '
            tolower($1) == "location:" {
                sub(/^[^:]+:[[:space:]]*/, "")
                sub(/\r$/, "")
                print
                exit
            }
        ')
        [[ "$actual" == "$expected" ]] || {
            printf 'built gateway %s%s redirected to %s, expected %s\n' \
                "$host" "$path" "${actual:-<none>}" "$expected" >&2
            exit 1
        }
    }

    require_gateway_status app.laggente.com /studio/conversazioni/validation 200
    require_gateway_status laggente.com /assets/does-not-exist.js 404
    require_gateway_status laggente.com /api/this-route-must-not-be-spa 404
    require_gateway_location \
        laggente.com '/studio?source=validation' \
        'https://app.laggente.com/studio?source=validation'
    require_gateway_location \
        app.laggente.com '/?source=validation' \
        'https://app.laggente.com/studio?source=validation'
    require_gateway_location \
        app.laggente.com '/mauro/conversazione?source=validation' \
        'https://mauro.laggente.com/conversazione?source=validation'
    require_gateway_status mauro.laggente.com /mauro 200

    docker rm -f "$gateway_validation_container" >/dev/null
    gateway_validation_container=
fi

printf 'infrastructure validation passed\n'
