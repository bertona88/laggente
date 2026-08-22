from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.request
from typing import Any
from urllib.parse import urlsplit

EXPECTED_PATH = "/api/v1/integrations/professional-email/inbound"
DEFAULT_ENDPOINT = f"https://app.laggente.com{EXPECTED_PATH}"
DEFAULT_MAX_BYTES = 5 * 1024 * 1024


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def _s3_client():
    import boto3

    return boto3.client("s3")


def _configuration() -> tuple[str, str, str, str, int]:
    bucket = os.environ.get("MAIL_BUCKET", "").strip()
    prefix = os.environ.get("MAIL_PREFIX", "incoming/").strip().lstrip("/")
    endpoint = os.environ.get("LAGGENTE_INBOUND_URL", DEFAULT_ENDPOINT).strip()
    secret = os.environ.get("LAGGENTE_INBOUND_SECRET", "")
    try:
        maximum = int(os.environ.get("MAIL_MAX_BYTES", str(DEFAULT_MAX_BYTES)))
    except ValueError as exc:
        raise RuntimeError("MAIL_MAX_BYTES is invalid") from exc
    parsed = urlsplit(endpoint)
    if (
        not bucket
        or len(secret) < 32
        or parsed.scheme != "https"
        or parsed.hostname != "app.laggente.com"
        or parsed.port not in {None, 443}
        or parsed.path != EXPECTED_PATH
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
        or maximum < 1024
        or maximum > 10 * 1024 * 1024
    ):
        raise RuntimeError("Email relay configuration is invalid")
    return bucket, prefix, endpoint, secret, maximum


def _ses_envelope(event: dict[str, Any]) -> tuple[str, str, str]:
    records = event.get("Records")
    if not isinstance(records, list) or len(records) != 1:
        raise RuntimeError("Expected exactly one SES record")
    ses = records[0].get("ses", {})
    mail = ses.get("mail", {})
    receipt = ses.get("receipt", {})
    receipt_id = str(mail.get("messageId", ""))
    received_at = str(mail.get("timestamp", ""))
    recipients = receipt.get("recipients")
    if (
        not receipt_id
        or len(receipt_id) > 500
        or "/" in receipt_id
        or receipt_id in {".", ".."}
        or not received_at
        or not isinstance(recipients, list)
        or len(recipients) != 1
        or not isinstance(recipients[0], str)
        or "@" not in recipients[0]
    ):
        raise RuntimeError("SES receipt envelope is invalid")
    return receipt_id, received_at, recipients[0]


def _open_request(request: urllib.request.Request, *, timeout: int):
    return urllib.request.build_opener(_NoRedirect).open(request, timeout=timeout)


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    bucket, prefix, endpoint, secret, maximum = _configuration()
    receipt_id, received_at, recipient = _ses_envelope(event)
    response = _s3_client().get_object(Bucket=bucket, Key=f"{prefix}{receipt_id}")
    raw = response["Body"].read(maximum + 1)
    if len(raw) > maximum:
        raise RuntimeError("Inbound message exceeds MAIL_MAX_BYTES")

    payload = json.dumps(
        {
            "recipient": recipient,
            "receipt_id": receipt_id,
            "raw_base64": base64.b64encode(raw).decode("ascii"),
            "received_at": received_at,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    timestamp = str(int(time.time()))
    signature = hmac.new(
        secret.encode("utf-8"),
        timestamp.encode("ascii") + b"." + payload,
        hashlib.sha256,
    ).hexdigest()
    request = urllib.request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Laggente-Timestamp": timestamp,
            "X-Laggente-Signature": f"sha256={signature}",
        },
    )
    with _open_request(request, timeout=10) as relay_response:
        relay_response.read(1024)
        status = relay_response.status
    if status not in {200, 201}:
        raise RuntimeError(f"LAGGENTE inbound endpoint returned HTTP {status}")
    return {"accepted": True, "receipt_id": receipt_id}
