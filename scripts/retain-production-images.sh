#!/usr/bin/env bash
set -Eeuo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=production-lib.sh
source "$script_dir/production-lib.sh"
require_command docker
require_command python3
configure_docker_client
exec python3 "$script_dir/retain-production-images.py" --root "$laggente_root" "$@"
