import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from app.providers.upstox_provider import UpstoxProvider

class TestUpstoxProvider(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Override config token for test
        self.patcher = patch("app.providers.upstox_provider.settings")
        self.mock_settings = self.patcher.start()
        self.mock_settings.UPSTOX_ACCESS_TOKEN = "mock_token"
        self.mock_settings.TRACK_EXPIRIES_COUNT = 2
        
        self.provider = UpstoxProvider()

    def tearDown(self):
        self.patcher.stop()

    def test_format_expiry_date(self):
        # YYYY-MM-DD format
        formatted = self.provider._format_expiry_date("2026-06-25")
        self.assertEqual(formatted, "25-Jun-2026")
        
        # Invalid format should fallback to input
        invalid = self.provider._format_expiry_date("invalid-date")
        self.assertEqual(invalid, "invalid-date")

    async def test_get_instrument_key_static(self):
        # Static mapping key should not trigger HTTP request
        mock_client = MagicMock()
        mock_client.get = AsyncMock()
        
        key = await self.provider._get_instrument_key(mock_client, "SENSEX")
        self.assertEqual(key, "BSE_INDEX|SENSEX")
        mock_client.get.assert_not_called()

    async def test_get_instrument_key_dynamic(self):
        # Setup mock response for search API
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": [
                {"symbol": "RELIANCE", "instrument_key": "NSE_EQ|INE002A01018"}
            ]
        }

        # Execute
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        
        key = await self.provider._get_instrument_key(mock_client, "RELIANCE")
        
        self.assertEqual(key, "NSE_EQ|INE002A01018")
        mock_client.get.assert_called_once()

    @patch("httpx.AsyncClient.get")
    async def test_fetch_option_chain_parsing(self, mock_get):
        # Mock active contracts response
        mock_contracts_response = MagicMock()
        mock_contracts_response.status_code = 200
        mock_contracts_response.json.return_value = {
            "status": "success",
            "data": [
                {"expiry": "2026-06-26", "strike_price": 80000, "instrument_type": "CE"},
                {"expiry": "2026-07-03", "strike_price": 80000, "instrument_type": "CE"}
            ]
        }
        
        # Mock option chain response
        mock_chain_response = MagicMock()
        mock_chain_response.status_code = 200
        mock_chain_response.json.return_value = {
            "status": "success",
            "data": [
                {
                    "expiry": "2026-06-26",
                    "strike_price": 80000.0,
                    "underlying_spot_price": 80100.5,
                    "call_options": {
                        "instrument_key": "BFO|80000CE",
                        "market_data": {
                            "ltp": 150.0,
                            "volume": 500,
                            "oi": 1000,
                            "prev_oi": 900,
                            "bid_price": 149.0,
                            "ask_price": 151.0
                        },
                        "option_greeks": {
                            "delta": 0.52,
                            "gamma": 0.0002,
                            "theta": -12.5,
                            "vega": 4.2,
                            "iv": 14.5
                        }
                    },
                    "put_options": {
                        "instrument_key": "BFO|80000PE",
                        "market_data": {
                            "ltp": 120.0,
                            "volume": 400,
                            "oi": 800,
                            "prev_oi": 850,
                            "bid_price": 119.0,
                            "ask_price": 121.0
                        },
                        "option_greeks": {
                            "delta": -0.48,
                            "gamma": 0.0002,
                            "theta": -10.5,
                            "vega": 4.0,
                            "iv": 15.0
                        }
                    }
                }
            ]
        }
        
        # Make mock_get return contracts response on first call, option chain on second and third calls
        mock_get.side_effect = [mock_contracts_response, mock_chain_response, mock_chain_response]

        # Execute
        results = await self.provider.fetch_option_chain("SENSEX")

        # Verify results
        self.assertEqual(len(results), 2)  # Two expiries tracked
        
        first_expiry = results[0]
        self.assertEqual(first_expiry["symbol"], "SENSEX")
        self.assertEqual(first_expiry["spot_price"], 80100.5)
        self.assertEqual(first_expiry["expiry_date"], "26-Jun-2026")
        self.assertEqual(first_expiry["expiry_dates"], ["26-Jun-2026", "03-Jul-2026"])
        
        strikes = first_expiry["strikes"]
        self.assertEqual(len(strikes), 1)
        
        strike = strikes[0]
        self.assertEqual(strike["strike"], 80000.0)
        self.assertEqual(strike["call_oi"], 1000)
        self.assertEqual(strike["call_change_oi"], 100) # 1000 - 900
        self.assertEqual(strike["call_volume"], 500)
        self.assertEqual(strike["call_ltp"], 150.0)
        self.assertEqual(strike["call_bid"], 149.0)
        self.assertEqual(strike["call_ask"], 151.0)
        self.assertEqual(strike["call_delta"], 0.52)
        
        self.assertEqual(strike["put_oi"], 800)
        self.assertEqual(strike["put_change_oi"], -50) # 800 - 850
        self.assertEqual(strike["put_volume"], 400)
        self.assertEqual(strike["put_ltp"], 120.0)
        self.assertEqual(strike["put_bid"], 119.0)
        self.assertEqual(strike["put_ask"], 121.0)
        self.assertEqual(strike["put_delta"], -0.48)

if __name__ == "__main__":
    unittest.main()
