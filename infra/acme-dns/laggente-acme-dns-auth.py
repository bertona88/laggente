#!/usr/bin/env python3
"""Certbot manual-auth hook for LAGGENTE's loopback-only acme-dns API."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


CREDENTIALS_PATH = Path("/etc/letsencrypt/laggente-acme-dns.json")
EXPECTED_API_URL = "http://127.0.0.1:5399/update"
EXPECTED_DOMAINS = {"laggente.com", "*.laggente.com"}
AUTHORITATIVE_SERVER = "116.203.123.0"


def fail(message: str) -> None:
    print(f"laggente-acme-dns: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_credentials() -> dict[str, str]:
    try:
        file_stat = CREDENTIALS_PATH.stat()
    except FileNotFoundError:
        fail(f"missing credentials file: {CREDENTIALS_PATH}")
    if file_stat.st_uid != 0 or stat.S_IMODE(file_stat.st_mode) & 0o077:
        fail("credentials file must be owned by root and inaccessible to group/other")
    try:
        payload = json.loads(CREDENTIALS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        fail("credentials file is unreadable or invalid JSON")
    required = ("username", "password", "subdomain", "fulldomain", "api_url")
    if any(not isinstance(payload.get(key), str) or not payload[key] for key in required):
        fail("credentials file is missing a required string field")
    if payload["api_url"] != EXPECTED_API_URL:
        fail("credentials API URL is not the fixed loopback endpoint")
    if not payload["fulldomain"].endswith(".auth.laggente.com"):
        fail("credentials target is outside auth.laggente.com")
    return payload


def update_challenge(credentials: dict[str, str], validation: str) -> None:
    body = json.dumps(
        {"subdomain": credentials["subdomain"], "txt": validation},
        separators=(",", ":"),
    ).encode("utf-8")
    request = urllib.request.Request(
        credentials["api_url"],
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Api-User": credentials["username"],
            "X-Api-Key": credentials["password"],
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status != 200:
                fail(f"challenge update returned HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        fail(f"challenge update returned HTTP {exc.code}")
    except urllib.error.URLError:
        fail("challenge update could not reach the loopback API")


def wait_for_authoritative_answer(fulldomain: str, validation: str) -> None:
    for _ in range(30):
        result = subprocess.run(
            [
                "dig",
                "+short",
                "TXT",
                fulldomain,
                f"@{AUTHORITATIVE_SERVER}",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and validation in result.stdout:
            # The authoritative answer is immediate. This short delay gives recursive
            # resolvers time to follow the stable delegation on a first issuance.
            time.sleep(5)
            return
        time.sleep(1)
    fail("authoritative DNS did not serve the new challenge within 30 seconds")


def main() -> None:
    domain = os.environ.get("CERTBOT_DOMAIN", "")
    validation = os.environ.get("CERTBOT_VALIDATION", "")
    if domain not in EXPECTED_DOMAINS:
        fail(f"refusing challenge for unexpected domain: {domain or '<missing>'}")
    if len(validation) < 32 or len(validation) > 255:
        fail("CERTBOT_VALIDATION has an unexpected length")
    credentials = load_credentials()
    update_challenge(credentials, validation)
    wait_for_authoritative_answer(credentials["fulldomain"], validation)


if __name__ == "__main__":
    main()
