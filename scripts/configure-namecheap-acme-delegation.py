#!/usr/bin/env python3
"""Configure LAGGENTE ACME delegation through an ephemeral Hetzner-origin API call.

Namecheap credentials are read locally and sent only to a short-lived Python
process over SSH stdin. They are never placed in an SSH command, server file,
or output. The remote process fetches the complete record set before applying
the three narrowly scoped delegation records.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path


SERVER_IP = "116.203.123.0"
REMOTE_RUNNER = r'''
import json
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

API_URL = "https://api.namecheap.com/xml.response"

def api_call(command, credentials, extra):
    params = dict(credentials)
    params.update({"Command": command, "SLD": "laggente", "TLD": "com"})
    params.update(extra)
    request = urllib.request.Request(
        API_URL,
        data=urllib.parse.urlencode(params).encode("utf-8"),
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        root = ET.fromstring(response.read())
    if root.attrib.get("Status") == "ERROR":
        errors = [
            (node.text or "").strip()
            for node in root.findall(".//{*}Error")
            if (node.text or "").strip()
        ]
        raise RuntimeError("; ".join(errors) or "Namecheap API returned ERROR")
    return root

def get_hosts(credentials):
    root = api_call("namecheap.domains.dns.getHosts", credentials, {})
    hosts = []
    for node in root.findall(".//{*}host"):
        record = {
            "host": node.attrib.get("Name", ""),
            "type": node.attrib.get("Type", "").upper(),
            "address": node.attrib.get("Address", ""),
            "ttl": node.attrib.get("TTL", "1800") or "1800",
        }
        if node.attrib.get("MXPref"):
            record["mx_pref"] = node.attrib["MXPref"]
        hosts.append(record)
    return hosts

def set_hosts(credentials, hosts):
    params = {}
    if any(record["type"] == "MX" for record in hosts):
        params["EmailType"] = "MX"
    for index, record in enumerate(hosts, start=1):
        params[f"HostName{index}"] = record["host"]
        params[f"RecordType{index}"] = record["type"]
        params[f"Address{index}"] = record["address"]
        params[f"TTL{index}"] = str(record.get("ttl") or "1800")
        if record["type"] == "MX" and record.get("mx_pref"):
            params[f"MXPref{index}"] = str(record["mx_pref"])
    api_call("namecheap.domains.dns.setHosts", credentials, params)

def normalized(value):
    return value.lower().rstrip(".")

payload = json.load(sys.stdin)
credentials = payload["credentials"]
before = get_hosts(credentials)
targets = [
    {"host": "auth", "type": "A", "address": "116.203.123.0", "ttl": "300"},
    {"host": "auth", "type": "NS", "address": "auth.laggente.com.", "ttl": "300"},
    {"host": "_acme-challenge", "type": "CNAME", "address": payload["fulldomain"].rstrip(".") + ".", "ttl": "300"},
]
target_keys = {(record["host"].lower(), record["type"]) for record in targets}
after = []
removed_challenge = []
for record in before:
    key = (record["host"].lower(), record["type"])
    if record["host"].lower() == "_acme-challenge":
        removed_challenge.append(record["type"])
        continue
    if key in target_keys:
        continue
    after.append(record)
after.extend(targets)

protected_before = sorted(
    (r["host"].lower(), r["type"], normalized(r["address"]), str(r.get("ttl", "")), str(r.get("mx_pref", "")))
    for r in before
    if r["host"].lower() not in {"auth", "_acme-challenge"}
)
plan = {
    "mode": "apply" if payload["apply"] else "dry-run",
    "before_count": len(before),
    "after_count": len(after),
    "preserved_records": len(protected_before),
    "removed_acme_challenge_types": sorted(removed_challenge),
    "upserts": ["auth A", "auth NS", "_acme-challenge CNAME"],
}
if not payload["apply"]:
    print(json.dumps(plan, sort_keys=True))
    raise SystemExit(0)

set_hosts(credentials, after)
readback = get_hosts(credentials)
protected_after = sorted(
    (r["host"].lower(), r["type"], normalized(r["address"]), str(r.get("ttl", "")), str(r.get("mx_pref", "")))
    for r in readback
    if r["host"].lower() not in {"auth", "_acme-challenge"}
)
if protected_after != protected_before:
    raise RuntimeError("protected DNS records changed during Namecheap readback")
for target in targets:
    if not any(
        r["host"].lower() == target["host"].lower()
        and r["type"] == target["type"]
        and normalized(r["address"]) == normalized(target["address"])
        for r in readback
    ):
        raise RuntimeError(f"required record missing after readback: {target['host']} {target['type']}")
plan["readback_count"] = len(readback)
plan["verified"] = True
print(json.dumps(plan, sort_keys=True))
'''


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    api_user = values.get("NAMECHEAP_API_USER") or values.get("NAMECHEAP_USERNAME")
    credentials = {
        "ApiUser": api_user or "",
        "ApiKey": values.get("NAMECHEAP_API_KEY", ""),
        "UserName": values.get("NAMECHEAP_USERNAME", ""),
        "ClientIp": values.get("NAMECHEAP_CLIENT_IP", ""),
    }
    missing = [key for key, value in credentials.items() if not value]
    if missing:
        raise ValueError(f"credential file is missing required fields: {', '.join(missing)}")
    if credentials["ClientIp"] != SERVER_IP:
        raise ValueError(f"NAMECHEAP_CLIENT_IP must be the stable Hetzner IP {SERVER_IP}")
    return credentials


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", required=True, type=Path, help="Local Namecheap credential file")
    parser.add_argument("--ssh-key", required=True, type=Path)
    parser.add_argument("--fulldomain", required=True, help="Registered acme-dns CNAME target")
    parser.add_argument("--apply", action="store_true", help="Write after the default dry run")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.fulldomain.rstrip(".").endswith(".auth.laggente.com"):
        print("fulldomain must be inside auth.laggente.com", file=sys.stderr)
        return 2
    try:
        credentials = load_env(args.env)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    payload = json.dumps(
        {
            "credentials": credentials,
            "fulldomain": args.fulldomain.rstrip("."),
            "apply": args.apply,
        },
        separators=(",", ":"),
    )
    command = [
        "ssh",
        "-i",
        os.fspath(args.ssh_key),
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=8",
        f"root@{SERVER_IP}",
        "python3",
        "-c",
        REMOTE_RUNNER,
    ]
    completed = subprocess.run(command, input=payload, text=True, check=False)
    if completed.returncode != 0:
        print("Namecheap delegation command failed", file=sys.stderr)
        return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
