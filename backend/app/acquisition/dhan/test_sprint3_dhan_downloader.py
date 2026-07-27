import unittest
from unittest.mock import MagicMock

from app.acquisition.dhan.client import DhanApiClient
from app.acquisition.dhan.downloader import RollingStrikeDownloader


class TestSprint3DhanDownloader(unittest.TestCase):
    """Unit test suite for Sprint 3: Rolling Strike Downloader & Date Paginator."""

    def setUp(self):
        self.mock_client = MagicMock(spec=DhanApiClient)
        self.downloader = RollingStrikeDownloader(client=self.mock_client)

    def test_01_fetch_strike_candles_window_dict_format(self):
        self.mock_client.post.return_value = {
            "status": "success",
            "data": {
                "start_Time": ["2024-05-15T09:15:00", "2024-05-15T09:16:00"],
                "open": [22500.0, 22510.0],
                "high": [22520.0, 22530.0],
                "low": [22490.0, 22505.0],
                "close": [22510.0, 22525.0],
                "volume": [100, 200],
                "open_interest": [5000, 5200],
                "implied_volatility": [15.2, 15.5],
                "spot_price": [22480.0, 22495.0]
            }
        }

        records = self.downloader.fetch_strike_candles_window(
            symbol="NIFTY",
            strike="ATM",
            option_type="CALL",
            from_date="2024-05-15",
            to_date="2024-05-15"
        )

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["timestamp"], "2024-05-15T09:15:00")
        self.assertEqual(records[0]["open"], 22500.0)
        self.assertEqual(records[0]["open_interest"], 5000)
        self.assertEqual(records[0]["spot_price"], 22480.0)

    def test_02_fetch_multi_month_pagination(self):
        self.mock_client.post.side_effect = [
            {
                "status": "success",
                "data": {
                    "start_Time": ["2024-05-01T09:15:00"],
                    "open": [22000.0],
                    "high": [22050.0],
                    "low": [21990.0],
                    "close": [22020.0],
                    "volume": [50],
                    "open_interest": [1000],
                    "spot_price": [22010.0]
                }
            },
            {
                "status": "success",
                "data": {
                    "start_Time": ["2024-06-01T09:15:00"],
                    "open": [22500.0],
                    "high": [22550.0],
                    "low": [22490.0],
                    "close": [22520.0],
                    "volume": [80],
                    "open_interest": [1200],
                    "spot_price": [22510.0]
                }
            }
        ]

        records = self.downloader.fetch_multi_month_strike(
            symbol="NIFTY",
            strike="ATM",
            option_type="CALL",
            start_date="2024-05-01",
            end_date="2024-06-15"
        )

        self.assertEqual(len(records), 2)
        self.assertEqual(self.mock_client.post.call_count, 2)
        self.assertEqual(records[0]["timestamp"], "2024-05-01T09:15:00")
        self.assertEqual(records[1]["timestamp"], "2024-06-01T09:15:00")


if __name__ == "__main__":
    unittest.main()
