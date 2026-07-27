import os
import unittest
from app.acquisition.dhan.config import DhanConfig, UNDERLYING_SECURITY_IDS, DEFAULT_RELATIVE_STRIKES
from app.acquisition.dhan.auth import DhanAuthenticator, DhanAuthError


class TestSprint1DhanAuth(unittest.TestCase):
    """Unit test suite for Sprint 1: Dhan Authentication & Configuration Manager."""

    def test_01_config_initialization(self):
        cfg = DhanConfig(client_id="TEST_CLIENT_123", access_token="TEST_TOKEN_XYZ")
        self.assertEqual(cfg.client_id, "TEST_CLIENT_123")
        self.assertEqual(cfg.access_token, "TEST_TOKEN_XYZ")
        self.assertTrue(cfg.is_configured())

    def test_02_config_missing_credentials(self):
        cfg = DhanConfig(client_id="", access_token="")
        self.assertFalse(cfg.is_configured())

    def test_03_auth_headers_generation(self):
        cfg = DhanConfig(client_id="CLIENT_ABC", access_token="TOKEN_DEF")
        auth = DhanAuthenticator(cfg)
        headers = auth.get_auth_headers()

        self.assertEqual(headers["client-id"], "CLIENT_ABC")
        self.assertEqual(headers["access-token"], "TOKEN_DEF")
        self.assertEqual(headers["Content-Type"], "application/json")

    def test_04_auth_header_raises_on_missing_creds(self):
        cfg = DhanConfig(client_id="", access_token="")
        auth = DhanAuthenticator(cfg)
        with self.assertRaises(DhanAuthError):
            auth.get_auth_headers()

    def test_05_constants_and_security_ids(self):
        self.assertEqual(UNDERLYING_SECURITY_IDS["NIFTY"], "13")
        self.assertEqual(UNDERLYING_SECURITY_IDS["BANKNIFTY"], "25")
        self.assertEqual(len(DEFAULT_RELATIVE_STRIKES), 21)
        self.assertIn("ATM", DEFAULT_RELATIVE_STRIKES)
        self.assertIn("ATM-10", DEFAULT_RELATIVE_STRIKES)
        self.assertIn("ATM+10", DEFAULT_RELATIVE_STRIKES)


if __name__ == "__main__":
    unittest.main()
