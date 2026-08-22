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
apt-get install -y \
    ca-certificates \
    curl \
    dbus-user-session \
    gnupg \
    jq \
    openssl \
    rsync \
    slirp4netns \
    uidmap

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
    "/home/$deploy_user/.config/systemd/user" \
    "/home/$deploy_user/.config/systemd/user/docker.service.d"
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

docker_network_dropin="/home/$deploy_user/.config/systemd/user/docker.service.d/10-laggente-network.conf"
docker_network_dropin_tmp=$(mktemp)
printf '%s\n' \
    '[Service]' \
    'Environment="DOCKERD_ROOTLESS_ROOTLESSKIT_NET=slirp4netns"' \
    'Environment="DOCKERD_ROOTLESS_ROOTLESSKIT_PORT_DRIVER=builtin"' \
    >"$docker_network_dropin_tmp"
docker_network_changed=false
if [[ ! -f "$docker_network_dropin" ]] || \
   ! cmp -s "$docker_network_dropin_tmp" "$docker_network_dropin"; then
    install -m 0600 -o "$deploy_user" -g "$deploy_group" \
        "$docker_network_dropin_tmp" "$docker_network_dropin"
    docker_network_changed=true
fi
rm -f -- "$docker_network_dropin_tmp"

runuser -u "$deploy_user" -- env XDG_RUNTIME_DIR="$runtime_dir" \
    systemctl --user daemon-reload
runuser -u "$deploy_user" -- env XDG_RUNTIME_DIR="$runtime_dir" \
    systemctl --user enable docker.service

docker_network_running=false
if ps -u "$deploy_user" -o args= | \
    grep -F 'rootlesskit ' | \
    grep -F -- '--net=slirp4netns' | \
    grep -F -- '--port-driver=builtin' >/dev/null; then
    docker_network_running=true
fi
if runuser -u "$deploy_user" -- env XDG_RUNTIME_DIR="$runtime_dir" \
    systemctl --user is-active --quiet docker.service; then
    if [[ "$docker_network_changed" == true || "$docker_network_running" != true ]]; then
        runuser -u "$deploy_user" -- env XDG_RUNTIME_DIR="$runtime_dir" \
            systemctl --user restart docker.service
    fi
else
    runuser -u "$deploy_user" -- env XDG_RUNTIME_DIR="$runtime_dir" \
        systemctl --user start docker.service
fi

rootless_docker() {
    runuser -u "$deploy_user" -- env \
        HOME="/home/$deploy_user" \
        XDG_RUNTIME_DIR="$runtime_dir" \
        DOCKER_HOST="unix://$runtime_dir/docker.sock" \
        docker "$@"
}

rootless_docker info >/dev/null
rootless_docker compose version >/dev/null
if ! command -v slirp4netns >/dev/null 2>&1; then
    printf 'slirp4netns is required for the rootless Docker network\n' >&2
    exit 1
fi
if ! ps -u "$deploy_user" -o args= | \
    grep -F 'rootlesskit ' | \
    grep -F -- '--net=slirp4netns' | \
    grep -F -- '--port-driver=builtin' >/dev/null; then
    printf 'rootless Docker did not start with slirp4netns and the builtin port driver\n' >&2
    exit 1
fi

rootless_network_check="laggente-rootless-network-check-$$"
cleanup_rootless_network_check() {
    rootless_docker rm -f "$rootless_network_check" >/dev/null 2>&1 || true
}
trap cleanup_rootless_network_check EXIT HUP INT TERM
rootless_docker run --detach --rm \
    --name "$rootless_network_check" \
    --publish "127.0.0.1:$loopback_port:8080" \
    alpine:3.21 \
    sh -c 'mkdir -p /srv && printf ready >/srv/index.html && exec busybox httpd -f -p 8080 -h /srv' \
    >/dev/null
rootless_network_published=$(rootless_docker port "$rootless_network_check" 8080/tcp)
if [[ "$rootless_network_published" != "127.0.0.1:$loopback_port" ]]; then
    printf 'rootless Docker did not publish the loopback validation port safely: %s\n' \
        "${rootless_network_published:-<none>}" >&2
    exit 1
fi
rootless_network_ready=false
for _attempt in {1..20}; do
    if curl --fail --silent --show-error --max-time 2 \
        "http://127.0.0.1:$loopback_port/" >/dev/null; then
        rootless_network_ready=true
        break
    fi
    sleep 0.25
done
if [[ "$rootless_network_ready" != true ]]; then
    printf 'rootless Docker loopback port forwarding did not become reachable\n' >&2
    exit 1
fi
cleanup_rootless_network_check
trap - EXIT HUP INT TERM

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
