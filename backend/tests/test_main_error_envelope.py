from __future__ import annotations

import unittest
from types import SimpleNamespace

import main


class MainErrorEnvelopeTests(unittest.TestCase):
    def test_error_payload_preserves_detail_and_request_id(self):
        request = SimpleNamespace(headers={"X-Request-Id": "req-123"})
        payload = main._error_payload(
            request=request,
            status_code=404,
            detail={"message": "missing"},
            fallback_message="Request failed",
        )
        self.assertEqual(payload["detail"], {"message": "missing"})
        self.assertEqual(payload["error"]["code"], "HTTP_404")
        self.assertEqual(payload["error"]["message"], "missing")
        self.assertEqual(payload["error"]["request_id"], "req-123")
        self.assertIsNone(payload["error"]["quality_reason"])

    def test_error_payload_uses_idempotency_key_when_request_id_missing(self):
        request = SimpleNamespace(headers={"Idempotency-Key": "idem-1"})
        payload = main._error_payload(
            request=request,
            status_code=500,
            detail="Internal server error",
            fallback_message="fallback",
        )
        self.assertEqual(payload["error"]["request_id"], "idem-1")
        self.assertEqual(payload["error"]["message"], "Internal server error")

    def test_error_message_fallback_when_detail_has_no_message(self):
        self.assertEqual(
            main._error_message_from_detail(detail={"oops": 1}, fallback="fallback-msg"),
            "fallback-msg",
        )
        self.assertEqual(
            main._error_message_from_detail(detail=["bad"], fallback="fallback-msg"),
            "fallback-msg",
        )


if __name__ == "__main__":
    unittest.main()
