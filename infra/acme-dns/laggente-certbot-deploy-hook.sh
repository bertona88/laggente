#!/usr/bin/env bash
set -Eeuo pipefail

expected_lineage=/etc/letsencrypt/live/laggente-wildcard
if [[ ${RENEWED_LINEAGE:-} != "$expected_lineage" ]]; then
    exit 0
fi

nginx -t
systemctl reload nginx
