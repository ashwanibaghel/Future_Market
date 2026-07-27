import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from app.acquisition.dhan.config import DhanConfig
from app.acquisition.dhan.client import DhanApiClient, DhanApiError, DhanRateLimitError
from app.acquisition.dhan.auth import DhanAuthError


class TestSprint2DhanClient(unittest.TestCase):
    """Unit test suite for Sprint 2: Rate-Limited DhanHQ HTTP API Client."""

    def setUp(self):
        self.config = DhanConfig(client_id="CLIENT_123", access_token="TOKEN_456", rate_limit_per_sec=50.0)
        self.client = DhanApiClient(self.config)

    @patch("urllib.request.urlopen")
    def test_01_successful_post_request(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"status": "success", "data": [1, 2, 3]}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        res = self.client.post("/charts/rollingoption", {"test": "payload"})
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["data"], [1, 2, 3])

    @patch("urllib.request.urlopen")
    def test_02_http_401_raises_api_error(self, mock_urlopen):
        mock_err = urllib.error.HTTPError(
            url="http://test",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=MagicMock(read=MagicMock(return_value=b'{"errorCode": "DH-901"}'))
        )
        mock_urlopen.side_effect = mock_err

        with self.assertRaises(DhanApiError) as ctx:
            self.client.post("/charts/rollingoption", {}, max_retries=1)
        self.assertEqual(ctx.exception.status_code, 401)

    @patch("urllib.request.urlopen")
    def test_03_http_429_retries_and_raises_rate_limit_error(self, mock_urlopen):
        mock_err = urllib.error.HTTPError(
            url="http://test",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=MagicMock(read=MagicMock(return_value=b'{"errorCode": "DH-429"}'))
        )
        mock_urlopen.side_effect = mock_err

        with self.assertRaises(DhanRateLimitError):
            self.client.post("/charts/rollingoption", {}, max_retries=2)
        self.assertEqual(mock_urlopen.call_count, 2)


if __name__ == "__main__":
    unittest.main()
