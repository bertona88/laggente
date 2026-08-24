from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import unittest
from unittest.mock import patch

import lambda_function


class _S3:
    def __init__(self, raw: bytes):
        self.raw = raw
        self.calls = []

    def get_object(self, **kwargs):
        self.calls.append(kwargs)
        return {"Body": io.BytesIO(self.raw)}


class _Response:
    status = 201

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _size):
        return b'{}'


class EmailRelayTest(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(
            os.environ,
            {
                "MAIL_BUCKET": "laggente-inbound-test",
                "MAIL_PREFIX": "incoming/",
                "LAGGENTE_INBOUND_URL": (
                    "https://app.laggente.com/api/v1/integrations/professional-email/inbound"
                ),
                "LAGGENTE_INBOUND_SECRET": "relay-test-secret-" + "x" * 32,
                "MAIL_MAX_BYTES": "5242880",
            },
            clear=True,
        )
        self.environment.start()

    def tearDown(self):
        self.environment.stop()

    def test_fetches_raw_s3_object_and_signs_exact_payload(self):
        raw = b"From: giulia@example.com\r\nTo: mauro@inbound.laggente.com\r\n\r\nCiao"
        s3 = _S3(raw)
        captured = {}

        def open_request(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return _Response()

        event = {
            "Records": [
                {
                    "ses": {
                        "mail": {
                            "messageId": "receipt-123",
                            "timestamp": "2026-08-23T10:00:00.000Z",
                        },
                        "receipt": {
                            "recipients": [
                                "mauro+5f6a7306-3859-4dc5-9403-d74348122f41@inbound.laggente.com"
                            ]
                        },
                    }
                }
            ]
        }
        with (
            patch.object(lambda_function, "_s3_client", return_value=s3),
            patch.object(lambda_function.time, "time", return_value=1_787_480_000),
            patch.object(lambda_function, "_open_request", side_effect=open_request),
        ):
            result = lambda_function.lambda_handler(event, None)

        self.assertEqual(result, {"accepted": True, "receipt_id": "receipt-123"})
        self.assertEqual(
            s3.calls, [{"Bucket": "laggente-inbound-test", "Key": "incoming/receipt-123"}]
        )
        request = captured["request"]
        self.assertEqual(captured["timeout"], 10)
        payload = request.data
        parsed = json.loads(payload)
        self.assertEqual(parsed["receipt_id"], "receipt-123")
        self.assertNotIn(raw, str(result).encode("utf-8"))
        expected = hmac.new(
            os.environ["LAGGENTE_INBOUND_SECRET"].encode("utf-8"),
            b"1787480000." + payload,
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(request.headers["X-laggente-signature"], f"sha256={expected}")

    def test_rejects_multiple_recipients(self):
        event = {
            "Records": [
                {
                    "ses": {
                        "mail": {"messageId": "receipt-123", "timestamp": "now"},
                        "receipt": {
                            "recipients": [
                                "mauro@inbound.laggente.com",
                                "other@inbound.laggente.com",
                            ]
                        },
                    }
                }
            ]
        }
        with self.assertRaisesRegex(RuntimeError, "envelope"):
            lambda_function.lambda_handler(event, None)


if __name__ == "__main__":
    unittest.main()
