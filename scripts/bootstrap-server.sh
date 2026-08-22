#!/usr/bin/env bash
set -Eeuo pipefail

deploy_user=laggente
authorized_keys_source=/root/.ssh/authorized_keys
loopback_port=45200

usage() {
    cat <<'EOF'
Usage: sudo ./scripts/bootstrap-server.sh [options]

Options:
  --deploy-user USER               Dedicated runtime user (default: laggente)
  --authorized-keys-source PATH    Existing authorized_keys to copy (default: /root/.ssh/authorized_keys)
  --loopback-port PORT             Host-only gateway port (default: 45200)
EOF
}

while (($#)); do
    case "$1" in
        --deploy-user)
            deploy_user=${2:?missing deploy user}
            shift 2
            ;;
        --authorized-keys-source)
            authorized_keys_source=${2:?missing authorized_keys path}
            shift 2
            ;;
        --loopback-port)
            loopback_port=${2:?missing loopback port}
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf 'unknown option: %s\n' "$1" >&2
            usage >&2
            exit 64
            ;;
    esac
done

if ((EUID != 0)); then
    printf 'run this bootstrap as root\n' >&2
    exit 1
fi

case "$loopback_port" in
    ''|*[!0-9]*) printf 'loopback port must be numeric\n' >&2; exit 64 ;;
esac
if ((loopback_port < 1024 || loopback_port > 65535)); then
    printf 'loopback port must be between 1024 and 65535\n' >&2
    exit 64
fi

if [[ ! -r /etc/os-release ]]; then
    printf 'cannot identify operating system\n' >&2
    exit 1
fi
. /etc/os-release
if [[ ${ID:-} != ubuntu || ${VERSION_ID:-} != 24.04 ]]; then
    printf 'expected Ubuntu 24.04; found %s %s\n' "${ID:-unknown}" "${VERSION_ID:-unknown}" >&2
    exit 1
fi

if ss -H -ltn "sport = :$loopback_port" | grep -q .; then
    printf 'TCP port %s is already occupied; refusing to continue\n' "$loopback_port" >&2
    exit 1
fi

if ! id "$deploy_user" >/dev/null 2>&1; then
    useradd --create-home --shell /bin/bash "$deploy_user"
fi
deploy_uid=$(id -u "$deploy_user")
deploy_group=$(id -gn "$deploy_user")

if [[ ! -r "$authorized_keys_source" ]]; then
    printf 'authorized key source is not readable: %s\n' "$authorized_keys_source" >&2
    exit 1
fi
install -d -m 0700 -o "$deploy_user" -g "$deploy_group" "/home/$deploy_user/.ssh"
install -m 0600 -o "$deploy_user" -g "$deploy_group" \
    "$authorized_keys_source" "/home/$deploy_user/.ssh/authorized_keys"

apt-get update
apt-get install -y ca-certificates curl gnupg openssl rsync jq uidmap dbus-user-session

conflicting_packages=()
for package in docker.io docker-compose docker-compose-v2 docker-doc docker-buildx podman-docker containerd runc; do
    if dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q 'install ok installed'; then
        conflicting_packages+=("$package")
    fi
done
if ((${#conflicting_packages[@]})); then
    printf 'conflicting container packages are installed: %s\n' "${conflicting_packages[*]}" >&2
    printf 'review and remove them explicitly before rerunning; this script will not uninstall packages automatically\n' >&2
    exit 1
fi

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
architecture=$(dpkg --print-architecture)
codename=${UBUNTU_CODENAME:-$VERSION_CODENAME}
printf '%s\n' \
    'Types: deb' \
    'URIs: https://download.docker.com/linux/ubuntu' \
    "Suites: $codename" \
    'Components: stable' \
    "Architectures: $architecture" \
    'Signed-By: /etc/apt/keyrings/docker.asc' \
    >/etc/apt/sources.list.d/docker.sources

apt-get update
apt-get install -y \
    docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin docker-ce-rootless-extras

if systemctl is-active --quiet docker.service; then
    if docker ps -aq 2>/dev/null | grep -q .; then
        printf 'the rootful Docker daemon contains containers; refusing to disable it on this shared host\n' >&2
        exit 1
    fi
fi
systemctl disable --now docker.service docker.socket || true
rm -f /var/run/docker.sock

install -d -m 0755 -o "$deploy_user" -g "$deploy_group" /opt/laggente
install -d -m 0750 -o "$deploy_user" -g "$deploy_group" \
    /opt/laggente/repo \
    /opt/laggente/releases \
    /opt/laggente/data \
    /opt/laggente/data/docker \
    /opt/laggente/data/postgres \
    /opt/laggente/data/uploads \
    /opt/laggente/data/backups
install -d -m 0750 -o root -g "$deploy_group" /opt/laggente/secrets

install -d -m 0700 -o "$deploy_user" -g "$deploy_group" "/home/$deploy_user/.config"
install -d -m 0700 -o "$deploy_user" -g "$deploy_group" \
    "/home/$deploy_user/.config/docker" \
    "/home/$deploy_user/.config/systemd" \
    "/home/$deploy_user/.config/systemd/user"
printf '{\n  "data-root": "/opt/laggente/data/docker",\n  "log-driver": "json-file",\n  "log-opts": {"max-size": "10m", "max-file": "3"}\n}\n' \
    >"/home/$deploy_user/.config/docker/daemon.json"
chown "$deploy_user:$deploy_group" "/home/$deploy_user/.config/docker/daemon.json"
chmod 0600 "/home/$deploy_user/.config/docker/daemon.json"

loginctl enable-linger "$deploy_user"
systemctl start "user@$deploy_uid.service"
runtime_dir="/run/user/$deploy_uid"

if [[ ! -f "/home/$deploy_user/.config/systemd/user/docker.service" ]]; then
    runuser -u "$deploy_user" -- env \
        HOME="/home/$deploy_user" \
        XDG_RUNTIME_DIR="$runtime_dir" \
        PATH="/usr/bin:/bin" \
        dockerd-rootless-setuptool.sh install
fi
runuser -u "$deploy_user" -- env XDG_RUNTIME_DIR="$runtime_dir" \
    systemctl --user enable --now docker.service

runuser -u "$deploy_user" -- env \
    HOME="/home/$deploy_user" \
    XDG_RUNTIME_DIR="$runtime_dir" \
    DOCKER_HOST="unix://$runtime_dir/docker.sock" \
    docker info >/dev/null
runuser -u "$deploy_user" -- env \
    HOME="/home/$deploy_user" \
    XDG_RUNTIME_DIR="$runtime_dir" \
    DOCKER_HOST="unix://$runtime_dir/docker.sock" \
    docker compose version >/dev/null

for secret_class in database application; do
    example="/opt/laggente/repo/infra/secrets/$secret_class.env.example"
    destination="/opt/laggente/secrets/$secret_class.env"
    if [[ -f "$example" && ! -e "$destination" ]]; then
        install -m 0640 -o root -g "$deploy_group" "$example" "$destination"
    fi
done

printf 'LAGGENTE server bootstrap completed.\n'
printf 'Next: populate /opt/laggente/secrets/database.env and application.env, then run deployment as %s.\n' "$deploy_user"
if [[ -e /opt/laggente/secrets/production.env ]]; then
    printf 'Legacy production.env was left untouched; current Compose releases ignore it.\n'
fi
printf 'No nginx, DNS, firewall, TLS, or application service was changed.\n'
