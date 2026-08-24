#!/usr/bin/env bash
set -Eeuo pipefail

key_file=.env.local
source_env=
database_output=.env.database.production.local
application_output=.env.application.production.local
pilot_email=
force=false
key_file_explicit=false
pilot_email_explicit=false

usage() {
    cat <<'EOF'
Usage:
  ./scripts/generate-production-env.sh --pilot-email EMAIL [options]
  ./scripts/generate-production-env.sh --source-env PATH [options]

Generate two least-privilege production env files without printing secret values.

Options:
  --key-file PATH             Read exactly one OPENAI_API_KEY from PATH
                              (default: .env.local)
  --source-env PATH           Split an existing combined production env file;
                              preserves secrets and applies current safe config
  --database-output PATH      Database output (default: .env.database.production.local)
  --application-output PATH   Application output (default: .env.application.production.local)
  --pilot-email EMAIL         Required when generating new credentials
  --force                     Replace the two local output files if they exist
  -h, --help                  Show this help

The outputs are local transfer artifacts with mode 0600. On the server, install
them as /opt/laggente/secrets/{database,application}.env, root:laggente 0640.
EOF
}

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

while (($#)); do
    case "$1" in
        --key-file)
            key_file=${2:?missing key file}
            key_file_explicit=true
            shift 2
            ;;
        --source-env)
            source_env=${2:?missing source env file}
            shift 2
            ;;
        --database-output)
            database_output=${2:?missing database output}
            shift 2
            ;;
        --application-output)
            application_output=${2:?missing application output}
            shift 2
            ;;
        --pilot-email)
            pilot_email=${2:?missing pilot email}
            pilot_email_explicit=true
            shift 2
            ;;
        --force)
            force=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "unknown option: $1"
            ;;
    esac
done

command -v awk >/dev/null 2>&1 || die 'awk is required'
command -v mktemp >/dev/null 2>&1 || die 'mktemp is required'

[[ "$database_output" != "$application_output" ]] || die 'output paths must be different'
[[ -d "$(dirname -- "$database_output")" ]] || die "database output directory does not exist"
[[ -d "$(dirname -- "$application_output")" ]] || die "application output directory does not exist"
if [[ "$force" != true ]]; then
    [[ ! -e "$database_output" ]] || die "output already exists: $database_output (use --force to replace both)"
    [[ ! -e "$application_output" ]] || die "output already exists: $application_output (use --force to replace both)"
fi

if [[ -n "$source_env" ]]; then
    [[ "$key_file_explicit" != true ]] || die '--source-env cannot be combined with --key-file'
    [[ "$pilot_email_explicit" != true ]] || die '--source-env cannot be combined with --pilot-email'
    [[ -r "$source_env" ]] || die "source env file is not readable: $source_env"
else
    [[ -r "$key_file" ]] || die "key file is not readable: $key_file"
    [[ -n "$pilot_email" ]] || die '--pilot-email is required when generating new credentials'
    case "$pilot_email" in
        *@*.*) ;;
        *) die '--pilot-email must look like an email address' ;;
    esac
    [[ "$pilot_email" != *[$'\r\n=']* ]] || die '--pilot-email contains an invalid character'
    command -v openssl >/dev/null 2>&1 || die 'openssl is required when generating credentials'
fi

umask 077
database_tmp=
application_tmp=
cleanup() {
    [[ -z "$database_tmp" ]] || rm -f -- "$database_tmp"
    [[ -z "$application_tmp" ]] || rm -f -- "$application_tmp"
}
trap cleanup EXIT HUP INT TERM
database_tmp=$(mktemp "${database_output}.tmp.XXXXXX")
application_tmp=$(mktemp "${application_output}.tmp.XXXXXX")
chmod 0600 "$database_tmp" "$application_tmp"

printf '%s\n' \
    '# Installed as /opt/laggente/secrets/database.env on production.' \
    '# Injected only into PostgreSQL, migrations, API, and backup.' \
    >"$database_tmp"
printf '%s\n' \
    '# Installed as /opt/laggente/secrets/application.env on production.' \
    '# Injected only into the API container.' \
    >"$application_tmp"

if [[ -n "$source_env" ]]; then
    database_keys='POSTGRES_USER,POSTGRES_DB,POSTGRES_PASSWORD,DATABASE_URL'
    application_keys='APP_ENV,SESSION_SECRET,BASE_DOMAIN,APP_ORIGIN,CORS_ORIGINS,TRUSTED_HOSTS,COOKIE_SECURE,SESSION_TTL_SECONDS,MAGIC_LINK_TTL_SECONDS,AUTH_MODE,PILOT_EMAIL,PILOT_PASSWORD,PILOT_NAME,SEED_DEMO,AUTO_CREATE_SCHEMA,PRODUCT_POSITIONING_JSON,OPENAI_API_KEY,OPENAI_MODEL,OPENAI_TRANSCRIPTION_MODEL,OPENAI_MAX_TURNS,RESEND_API_KEY,RESEND_WEBHOOK_SECRET,FROM_EMAIL,AGENT_MAIL_ENABLED,AGENT_MAIL_PROVIDER,AGENT_MAIL_FROM_DOMAIN,AGENT_MAIL_REPLY_DOMAIN,AGENT_MAIL_AWS_REGION,AGENT_MAIL_INBOUND_SECRET,AGENT_MAIL_MAX_INBOUND_BYTES,AWS_ACCESS_KEY_ID,AWS_SECRET_ACCESS_KEY,AWS_SESSION_TOKEN,UPLOAD_DIR,MAX_UPLOAD_BYTES,CONVERSATION_RETENTION_DAYS,PRIVACY_NOTICE_VERSION'
    application_required='APP_ENV,SESSION_SECRET,BASE_DOMAIN,APP_ORIGIN,CORS_ORIGINS,TRUSTED_HOSTS,COOKIE_SECURE,AUTH_MODE,PILOT_EMAIL,PILOT_PASSWORD,PILOT_NAME,SEED_DEMO,AUTO_CREATE_SCHEMA,OPENAI_API_KEY,OPENAI_MODEL,UPLOAD_DIR,MAX_UPLOAD_BYTES'

    awk \
        -v database_keys="$database_keys" \
        -v application_keys="$application_keys" \
        -v application_required="$application_required" \
        -v database_output="$database_tmp" \
        -v application_output="$application_tmp" '
        BEGIN {
            database_count = split(database_keys, parts, ",")
            for (idx = 1; idx <= database_count; idx += 1) {
                database[parts[idx]] = 1
                required[parts[idx]] = 1
            }
            delete parts
            application_count = split(application_keys, parts, ",")
            for (idx = 1; idx <= application_count; idx += 1) application[parts[idx]] = 1
            delete parts
            required_count = split(application_required, parts, ",")
            for (idx = 1; idx <= required_count; idx += 1) required[parts[idx]] = 1
        }
        /^[[:space:]]*($|#)/ { next }
        !/^[A-Z][A-Z0-9_]*=/ {
            print "error: invalid source env syntax on line " NR > "/dev/stderr"
            invalid = 1
            next
        }
        {
            separator = index($0, "=")
            key = substr($0, 1, separator - 1)
            value = substr($0, separator + 1)
            seen[key] += 1
            if (seen[key] > 1) {
                print "error: source env repeats key " key > "/dev/stderr"
                invalid = 1
                next
            }
            if (!(key in database) && !(key in application)) {
                print "error: source env contains disallowed key " key > "/dev/stderr"
                invalid = 1
                next
            }
            if ((key in required) && (length(value) == 0 || value ~ /^REPLACE_/)) {
                print "error: source env has an empty or placeholder value for " key > "/dev/stderr"
                invalid = 1
                next
            }
            if (key in database) print $0 >> database_output
            else if (key == "APP_ENV") print "APP_ENV=production" >> application_output
            else if (key == "BASE_DOMAIN") print "BASE_DOMAIN=laggente.com" >> application_output
            else if (key == "APP_ORIGIN") print "APP_ORIGIN=https://app.laggente.com" >> application_output
            else if (key == "CORS_ORIGINS") print "CORS_ORIGINS=https://app.laggente.com" >> application_output
            else if (key == "TRUSTED_HOSTS") print "TRUSTED_HOSTS=laggente.com,*.laggente.com" >> application_output
            else if (key == "COOKIE_SECURE") print "COOKIE_SECURE=true" >> application_output
            else if (key == "AUTO_CREATE_SCHEMA") print "AUTO_CREATE_SCHEMA=false" >> application_output
            else print $0 >> application_output
        }
        END {
            for (key in required) {
                if (!(key in seen)) {
                    print "error: source env is missing required key " key > "/dev/stderr"
                    invalid = 1
                }
            }
            exit invalid ? 1 : 0
        }
    ' "$source_env" || die 'source env could not be split safely'
    if ! grep -q '^CONVERSATION_RETENTION_DAYS=' "$application_tmp"; then
        printf '%s\n' 'CONVERSATION_RETENTION_DAYS=365' >>"$application_tmp"
    fi
    if ! grep -q '^PRIVACY_NOTICE_VERSION=' "$application_tmp"; then
        printf '%s\n' 'PRIVACY_NOTICE_VERSION=2026-08-22.2' >>"$application_tmp"
    fi
    if ! grep -q '^AGENT_MAIL_ENABLED=' "$application_tmp"; then
        printf '%s\n' 'AGENT_MAIL_ENABLED=false' >>"$application_tmp"
    fi
    if ! grep -q '^RESEND_WEBHOOK_SECRET=' "$application_tmp"; then
        printf '%s\n' 'RESEND_WEBHOOK_SECRET=' >>"$application_tmp"
    fi
else
    openai_key=$(awk '
        /^[[:space:]]*($|#)/ { next }
        /^OPENAI_API_KEY=/ {
            count += 1
            value = substr($0, index($0, "=") + 1)
        }
        END {
            if (count != 1 || length(value) == 0 || value ~ /^REPLACE_/) exit 1
            print value
        }
    ' "$key_file") || die "expected exactly one nonempty OPENAI_API_KEY in $key_file"

    postgres_password=$(openssl rand -hex 24)
    session_secret=$(openssl rand -hex 48)
    pilot_password=$(openssl rand -hex 18)

    printf '%s\n' \
        'POSTGRES_USER=laggente' \
        'POSTGRES_DB=laggente' \
        "POSTGRES_PASSWORD=$postgres_password" \
        "DATABASE_URL=postgresql+psycopg://laggente:$postgres_password@db:5432/laggente" \
        >>"$database_tmp"

    printf '%s\n' \
        'APP_ENV=production' \
        "SESSION_SECRET=$session_secret" \
        'BASE_DOMAIN=laggente.com' \
        'APP_ORIGIN=https://app.laggente.com' \
        'CORS_ORIGINS=https://app.laggente.com' \
        'TRUSTED_HOSTS=laggente.com,*.laggente.com' \
        'COOKIE_SECURE=true' \
        'SESSION_TTL_SECONDS=1209600' \
        'MAGIC_LINK_TTL_SECONDS=900' \
        'AUTH_MODE=pilot_password' \
        "PILOT_EMAIL=$pilot_email" \
        "PILOT_PASSWORD=$pilot_password" \
        'PILOT_NAME=Mauro Rossi' \
        'SEED_DEMO=true' \
        'AUTO_CREATE_SCHEMA=false' \
        'PRODUCT_POSITIONING_JSON={"audience":"Professionisti che lavorano attraverso relazioni, competenza e fiducia, a partire dagli agenti immobiliari.","opening_question":"Che lavoro fai?","featured_verticals":[{"id":"real_estate_it","label":"Agenti immobiliari","weight":100,"status":"pilot","template_id":"seller_it_v1","example_answer":"Sono un agente immobiliare a Roma Nord. Prima di valutare un immobile controllo titolo di provenienza, conformità urbanistica e catastale, APE, occupazione e vincoli.","headline":"Partiamo dagli agenti immobiliari.","description":"Il primo settore reso concreto dal pilot italiano, senza trasformare la conversazione in una pipeline."}]}' \
        "OPENAI_API_KEY=$openai_key" \
        'OPENAI_MODEL=gpt-5.6' \
        'OPENAI_TRANSCRIPTION_MODEL=gpt-4o-mini-transcribe' \
        'OPENAI_MAX_TURNS=6' \
        'RESEND_API_KEY=' \
        'RESEND_WEBHOOK_SECRET=' \
        'FROM_EMAIL=' \
        'AGENT_MAIL_ENABLED=false' \
        'AGENT_MAIL_PROVIDER=capture' \
        'AGENT_MAIL_FROM_DOMAIN=laggente.com' \
        'AGENT_MAIL_REPLY_DOMAIN=inbound.laggente.com' \
        'AGENT_MAIL_AWS_REGION=eu-south-1' \
        'AGENT_MAIL_INBOUND_SECRET=' \
        'AGENT_MAIL_MAX_INBOUND_BYTES=5242880' \
        'AWS_ACCESS_KEY_ID=' \
        'AWS_SECRET_ACCESS_KEY=' \
        'AWS_SESSION_TOKEN=' \
        'UPLOAD_DIR=/data/uploads' \
        'MAX_UPLOAD_BYTES=10485760' \
        'CONVERSATION_RETENTION_DAYS=365' \
        'PRIVACY_NOTICE_VERSION=2026-08-22.2' \
        >>"$application_tmp"
fi

mv -f -- "$database_tmp" "$database_output"
mv -f -- "$application_tmp" "$application_output"
trap - EXIT HUP INT TERM

printf 'created %s (mode 0600)\n' "$database_output"
printf 'created %s (mode 0600)\n' "$application_output"
printf 'secret values were not printed; transfer each file through SSH stdin\n'
