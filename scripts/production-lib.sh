#!/usr/bin/env bash

set -Eeuo pipefail

readonly LAGGENTE_DEFAULT_ROOT=/opt/laggente
readonly LAGGENTE_DEFAULT_PORT=45200

laggente_root=${LAGGENTE_ROOT:-$LAGGENTE_DEFAULT_ROOT}
laggente_repo=${LAGGENTE_REPO:-$laggente_root/repo}
laggente_database_env_file=${LAGGENTE_DATABASE_ENV_FILE:-$laggente_root/secrets/database.env}
laggente_application_env_file=${LAGGENTE_APPLICATION_ENV_FILE:-$laggente_root/secrets/application.env}
laggente_releases_dir=${LAGGENTE_RELEASES_DIR:-$laggente_root/releases}
laggente_loopback_port=${LAGGENTE_LOOPBACK_PORT:-$LAGGENTE_DEFAULT_PORT}

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

note() {
    printf '==> %s\n' "$*"
}

require_unused_release_path() {
    local candidate=$1
    if [[ -e "$candidate" || -L "$candidate" ]]; then
        die "release metadata already exists and is immutable: $candidate"
    fi
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

configure_docker_client() {
    local runtime_dir="/run/user/$(id -u)"
    if [[ -S "$runtime_dir/docker.sock" ]]; then
        export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-$runtime_dir}
        export DOCKER_HOST=${DOCKER_HOST:-unix://$runtime_dir/docker.sock}
    fi
}

require_repo() {
    [[ -f "$laggente_repo/compose.yaml" ]] || die "compose file not found at $laggente_repo/compose.yaml"
}

require_restricted_env_file() {
    local env_file=$1
    local label=$2
    [[ -r "$env_file" ]] || die "$label secrets are not readable at $env_file"
    local permissions
    permissions=$(stat -c '%a' "$env_file")
    case "$permissions" in
        640) ;;
        *) die "$label secrets must have mode 0640, found $permissions" ;;
    esac
    local ownership
    ownership=$(stat -c '%U:%G' "$env_file")
    [[ "$ownership" == "root:$(id -gn)" ]] || \
        die "$label secrets must be owned by root:$(id -gn), found $ownership"
}

require_allowed_env_keys() {
    local env_file=$1
    local label=$2
    local allowed_csv=$3
    awk -v label="$label" -v allowed_csv="$allowed_csv" '
        BEGIN {
            count = split(allowed_csv, allowed_keys, ",")
            for (idx = 1; idx <= count; idx += 1) allowed[allowed_keys[idx]] = 1
        }
        /^[[:space:]]*($|#)/ { next }
        !/^[A-Z][A-Z0-9_]*=/ {
            print "error: invalid " label " env syntax on line " NR > "/dev/stderr"
            invalid = 1
            next
        }
        {
            key = substr($0, 1, index($0, "=") - 1)
            seen[key] += 1
            if (!(key in allowed)) {
                print "error: " label " env contains disallowed key " key > "/dev/stderr"
                invalid = 1
            }
            if (seen[key] > 1) {
                print "error: " label " env repeats key " key > "/dev/stderr"
                invalid = 1
            }
        }
        END { exit invalid ? 1 : 0 }
    ' "$env_file" || die "$label secret-key boundary validation failed"
}

require_env_value() {
    local env_file=$1
    local variable=$2
    local label=$3
    if ! awk -F= -v wanted="$variable" '
        $1 == wanted {
            value = substr($0, index($0, "=") + 1)
            if (length(value) > 0 && value !~ /^REPLACE_/) found = 1
        }
        END { exit found ? 0 : 1 }
    ' "$env_file"; then
        die "$variable is absent, empty, or still a placeholder in $label secrets"
    fi
}

require_env_exact_value() {
    local env_file=$1
    local variable=$2
    local expected=$3
    local label=$4
    if ! awk -v wanted="$variable" -v expected="$expected" '
        index($0, "=") > 0 && substr($0, 1, index($0, "=") - 1) == wanted {
            value = substr($0, index($0, "=") + 1)
            if (value == expected) found = 1
        }
        END { exit found ? 0 : 1 }
    ' "$env_file"; then
        die "$variable in $label secrets must equal the production-safe value"
    fi
}

require_production_application_contract() {
    local env_file=$1
    local label=${2:-application}

    require_env_exact_value "$env_file" APP_ENV production "$label"
    require_env_exact_value "$env_file" BASE_DOMAIN laggente.com "$label"
    require_env_exact_value \
        "$env_file" APP_ORIGIN https://app.laggente.com "$label"
    require_env_exact_value \
        "$env_file" CORS_ORIGINS https://app.laggente.com "$label"
    require_env_exact_value \
        "$env_file" TRUSTED_HOSTS 'laggente.com,*.laggente.com' "$label"
    require_env_exact_value "$env_file" COOKIE_SECURE true "$label"
    require_env_exact_value "$env_file" AUTO_CREATE_SCHEMA false "$label"
}

require_secret_files() {
    local database_allowed
    local application_allowed
    database_allowed='POSTGRES_USER,POSTGRES_DB,POSTGRES_PASSWORD,DATABASE_URL'
    application_allowed='APP_ENV,SESSION_SECRET,BASE_DOMAIN,APP_ORIGIN,CORS_ORIGINS,TRUSTED_HOSTS,COOKIE_SECURE,SESSION_TTL_SECONDS,MAGIC_LINK_TTL_SECONDS,AUTH_MODE,PILOT_EMAIL,PILOT_PASSWORD,PILOT_NAME,SEED_DEMO,AUTO_CREATE_SCHEMA,PRODUCT_POSITIONING_JSON,OPENAI_API_KEY,OPENAI_MODEL,OPENAI_TRANSCRIPTION_MODEL,OPENAI_MAX_TURNS,RESEND_API_KEY,RESEND_WEBHOOK_SECRET,FROM_EMAIL,AGENT_MAIL_ENABLED,AGENT_MAIL_PROVIDER,AGENT_MAIL_FROM_DOMAIN,AGENT_MAIL_REPLY_DOMAIN,AGENT_MAIL_AWS_REGION,AGENT_MAIL_INBOUND_SECRET,AGENT_MAIL_MAX_INBOUND_BYTES,AWS_ACCESS_KEY_ID,AWS_SECRET_ACCESS_KEY,AWS_SESSION_TOKEN,UPLOAD_DIR,MAX_UPLOAD_BYTES,CONVERSATION_RETENTION_DAYS,PRIVACY_NOTICE_VERSION'

    require_restricted_env_file "$laggente_database_env_file" database
    require_restricted_env_file "$laggente_application_env_file" application
    require_allowed_env_keys "$laggente_database_env_file" database "$database_allowed"
    require_allowed_env_keys "$laggente_application_env_file" application "$application_allowed"

    local variable
    for variable in POSTGRES_USER POSTGRES_DB POSTGRES_PASSWORD DATABASE_URL; do
        require_env_value "$laggente_database_env_file" "$variable" database
    done
    for variable in \
        APP_ENV SESSION_SECRET BASE_DOMAIN APP_ORIGIN CORS_ORIGINS TRUSTED_HOSTS \
        COOKIE_SECURE AUTH_MODE PILOT_EMAIL PILOT_PASSWORD PILOT_NAME SEED_DEMO \
        AUTO_CREATE_SCHEMA OPENAI_API_KEY OPENAI_MODEL UPLOAD_DIR MAX_UPLOAD_BYTES \
        CONVERSATION_RETENTION_DAYS PRIVACY_NOTICE_VERSION; do
        require_env_value "$laggente_application_env_file" "$variable" application
    done
    require_production_application_contract "$laggente_application_env_file" application
}

compose_with_release() {
    local release_env=$1
    shift
    docker compose \
        --project-directory "$laggente_repo" \
        --file "$laggente_repo/compose.yaml" \
        --env-file "$release_env" \
        "$@"
}

inspect_published_port_bindings() {
    local container_port=$1
    [[ "$container_port" =~ ^[1-9][0-9]{0,4}$ ]] && \
        ((10#$container_port <= 65535)) || \
        die "invalid container port: $container_port"

    # Docker records an exposed-but-unpublished port as a JSON null in
    # NetworkSettings.Ports. Only a non-empty bindings array represents a host
    # publication. Keep this distinction explicit instead of relying on
    # `docker compose port`, whose output also includes exposed ports in some
    # Compose versions.
    jq -r --arg port "${container_port}/tcp" '
        if (type != "array") or (length != 1) then
            error("expected exactly one Docker inspect object")
        else
            .[0].NetworkSettings.Ports[$port] as $bindings
            | if $bindings == null then
                empty
              elif ($bindings | type) != "array" then
                error("Docker port bindings are not an array or null")
              else
                $bindings[]
                | if ((.HostIp | type) != "string") or
                     ((.HostPort | type) != "string") then
                    error("Docker port binding is missing HostIp or HostPort")
                  elif (.HostIp | contains(":")) then
                    "[\(.HostIp)]:\(.HostPort)"
                  else
                    "\(.HostIp):\(.HostPort)"
                  end
              end
        end
    '
}

compose_service_published_bindings() {
    local release_env=$1
    local service=$2
    local container_port=$3
    local container_id

    container_id=$(compose_with_release "$release_env" ps --all --quiet "$service")
    [[ -n "$container_id" ]] || die "no container found for service $service"
    [[ "$container_id" != *$'\n'* ]] || \
        die "multiple containers found for singleton service $service"

    docker inspect "$container_id" | inspect_published_port_bindings "$container_port"
}

wait_for_http() {
    local url=$1
    local host=$2
    local attempts=${3:-40}
    local delay=${4:-3}
    local attempt

    for ((attempt = 1; attempt <= attempts; attempt += 1)); do
        if curl --fail --silent --show-error --max-time 5 --header "Host: $host" "$url" >/dev/null; then
            return 0
        fi
        sleep "$delay"
    done
    return 1
}

wait_for_gateway() {
    wait_for_http "http://127.0.0.1:$laggente_loopback_port/_gateway_health" laggente.com 40 3 &&
        wait_for_http "http://127.0.0.1:$laggente_loopback_port/api/readyz" laggente.com 20 3
}

validate_release_id() {
    local release_id=$1
    [[ "$release_id" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$ ]] || \
        die "release id must be 1-80 safe filename characters"
    case "$release_id" in
        current|previous) die "release id is reserved for release pointers: $release_id" ;;
    esac
}

assert_capacity() {
    local minimum_kib=${1:-4194304}
    local available_kib
    available_kib=$(df -Pk "$laggente_root" | awk 'NR == 2 {print $4}')
    [[ "$available_kib" =~ ^[0-9]+$ ]] || die "could not determine available disk"
    if ((available_kib < minimum_kib)); then
        die "less than $((minimum_kib / 1024 / 1024)) GiB is free under $laggente_root"
    fi
}
