#!/usr/bin/env bash
set -Eeuo pipefail

# Upstream 2.0.2's release binary predates the Go trust-store security fix.
# Build the same reviewed source with a pinned, patched compiler instead.
source_commit=4e5a69e5fb742dde4f755b7f56aee2aea76e19bf
source_sha256=9d90a0f7ffe8127cdfebe59b33fa3e71050fd05aab40fc37af55d1f3e5a10377
go_version=1.27.3
go_linux_sha256=65efbc80fdc1fa2cd2631cad5b481777a68e8725f34e89f50fc6ac714e379b40

if [[ $# != 1 ]]; then
    printf 'usage: %s OUTPUT_DIRECTORY\n' "$0" >&2
    exit 64
fi
mkdir -p -- "$1"
output_dir=$(cd -- "$1" && pwd)
build_tmp=$(mktemp -d)
trap 'rm -rf -- "$build_tmp"' EXIT HUP INT TERM

verify_digest() {
    local expected=$1 archive=$2 actual
    if command -v sha256sum >/dev/null 2>&1; then
        actual=$(sha256sum "$archive")
    else
        actual=$(shasum -a 256 "$archive")
    fi
    [[ ${actual%% *} == "$expected" ]] || {
        printf 'security build archive digest mismatch\n' >&2
        exit 65
    }
}

go_bin=${ACME_DNS_GO_BIN:-}
if [[ -z $go_bin ]]; then
    if [[ $(uname -s) != Linux || $(uname -m) != x86_64 ]]; then
        printf 'set ACME_DNS_GO_BIN to an installed Go %s compiler on this host\n' "$go_version" >&2
        exit 69
    fi
    curl --fail --silent --show-error --location \
        "https://go.dev/dl/go${go_version}.linux-amd64.tar.gz" \
        --output "$build_tmp/go.tar.gz"
    verify_digest "$go_linux_sha256" "$build_tmp/go.tar.gz"
    tar -xzf "$build_tmp/go.tar.gz" -C "$build_tmp"
    go_bin="$build_tmp/go/bin/go"
fi
if [[ $(GOTOOLCHAIN=local "$go_bin" env GOVERSION) != "go${go_version}" ]]; then
    printf 'acme-dns requires the pinned Go %s compiler\n' "$go_version" >&2
    exit 65
fi
curl --fail --silent --show-error --location \
    "https://codeload.github.com/acme-dns/acme-dns/tar.gz/${source_commit}" \
    --output "$build_tmp/source.tar.gz"
verify_digest "$source_sha256" "$build_tmp/source.tar.gz"
mkdir "$build_tmp/source"
tar -xzf "$build_tmp/source.tar.gz" --strip-components=1 -C "$build_tmp/source"
(
    cd "$build_tmp/source"
    CGO_ENABLED=0 GOOS=linux GOARCH=amd64 GOTOOLCHAIN=local \
        "$go_bin" build -trimpath -buildvcs=false -ldflags='-s -w' \
        -o "$output_dir/acme-dns" .
)
cp "$build_tmp/source/LICENSE" "$output_dir/LICENSE"
printf 'Built acme-dns 2.0.2 (%s) with Go %s\n' "$source_commit" "$go_version"
