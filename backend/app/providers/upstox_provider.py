import httpx
import json
import logging
from typing import Dict, Any, List
from datetime import datetime
from app.providers.base import BaseProvider
from app.config import settings

logger = logging.getLogger(__name__)

SYMBOL_MAP = {
    "SENSEX": "BSE_INDEX|SENSEX",
    "NIFTY": "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
    "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
    "MIDCPNIFTY": "NSE_INDEX|Nifty Midcap 50",
}

class UpstoxProvider(BaseProvider):
    def __init__(self):
        self.base_url = "https://api.upstox.com"
        self.access_token = settings.UPSTOX_ACCESS_TOKEN

    def _format_expiry_date(self, date_str: str) -> str:
        """
        Converts '2026-06-30' -> '30-Jun-2026' for UI and DB consistency.
        """
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.strftime("%d-%b-%Y")
        except Exception:
            return date_str

    async def _get_instrument_key(self, client: httpx.AsyncClient, symbol: str) -> str:
        """
        Determines the instrument key for a symbol. Uses static map or falls back to search API.
        """
        if symbol in SYMBOL_MAP:
            return SYMBOL_MAP[symbol]

        # Fallback: Instrument Search API
        url = f"{self.base_url}/v2/instruments/search"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.access_token}"
        }
        params = {"query": symbol}
        
        try:
            logger.info(f"Querying Upstox search API for instrument key: {symbol}...")
            response = await client.get(url, headers=headers, params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            results = data.get("data", [])
            
            # Find the best match where symbol matches exactly
            for item in results:
                if item.get("symbol") == symbol:
                    key = item.get("instrument_key")
                    logger.info(f"Resolved key for {symbol} dynamically: {key}")
                    return key
            
            if results:
                key = results[0].get("instrument_key")
                logger.info(f"Resolved key for {symbol} using first search result: {key}")
                return key
        except Exception as e:
            logger.error(f"Failed to dynamically search instrument key for {symbol}: {str(e)}")
            
        # Absolute fallback guessing exchange
        if symbol in ["SENSEX"]:
            return "BSE_INDEX|SENSEX"
        return f"NSE_INDEX|{symbol}"

    async def fetch_option_chain(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Fetches options contract expiries and crawls the option chains for top expiries from Upstox.
        """
        if not self.access_token or self.access_token == "YOUR_PASTED_ACCESS_TOKEN_HERE":
            logger.error("Upstox Access Token is missing or not configured in settings/environment.")
            raise ValueError("Upstox Access Token is not set. Please paste it in your .env file.")

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.access_token}"
        }

        async with httpx.AsyncClient(follow_redirects=True) as client:
            # Step 1: Resolve instrument key
            instrument_key = await self._get_instrument_key(client, symbol)
            
            # Step 2: Fetch active option contracts to extract unique expiries
            contracts_url = f"{self.base_url}/v2/option/contract"
            params = {"instrument_key": instrument_key}
            
            try:
                logger.info(f"Fetching active option contracts for key {instrument_key}...")
                response = await client.get(contracts_url, headers=headers, params=params, timeout=10.0)
                response.raise_for_status()
                contracts_data = response.json()
            except Exception as e:
                logger.error(f"Failed to fetch active option contracts for {symbol} ({instrument_key}): {str(e)}")
                raise e

            contracts = contracts_data.get("data", [])
            if not contracts:
                logger.warning(f"No option contracts found in Upstox response for {symbol}")
                return []

            # Extract unique expiries (e.g. YYYY-MM-DD)
            unique_expiries = list(set(c.get("expiry") for c in contracts if c.get("expiry")))
            
            def parse_date(date_str):
                try:
                    return datetime.strptime(date_str, "%Y-%m-%d")
                except Exception:
                    return datetime.max
                    
            unique_expiries.sort(key=parse_date)
            
            if not unique_expiries:
                logger.warning(f"No valid expiry dates extracted from option contracts for {symbol}")
                return []

            logger.info(f"Found active expiries for {symbol}: {unique_expiries}")
            
            # Select top expiries
            tracked_expiries = unique_expiries[:settings.TRACK_EXPIRIES_COUNT]
            
            results = []
            
            # Step 3: Fetch full option chain for each tracked expiry
            chain_url = f"{self.base_url}/v2/option/chain"
            for expiry in tracked_expiries:
                chain_params = {
                    "instrument_key": instrument_key,
                    "expiry_date": expiry
                }
                
                try:
                    logger.info(f"Fetching option chain for {symbol} on expiry {expiry}...")
                    chain_response = await client.get(chain_url, headers=headers, params=chain_params, timeout=10.0)
                    chain_response.raise_for_status()
                    chain_payload = chain_response.json()
                except Exception as e:
                    logger.error(f"Failed to fetch option chain for {symbol} expiry {expiry}: {str(e)}")
                    continue
                
                chain_data = chain_payload.get("data", [])
                if not chain_data:
                    logger.warning(f"Empty option chain data for {symbol} expiry {expiry}")
                    continue

                # Extract spot price from the first row of option chain
                spot_price = 0.0
                for row in chain_data:
                    spot = row.get("underlying_spot_price")
                    if spot:
                        spot_price = float(spot)
                        break
                        
                parsed_strikes = []
                for row in chain_data:
                    strike = float(row.get("strike_price", 0.0))
                    if strike == 0.0:
                        continue
                        
                    # Call Option Details
                    ce = row.get("call_options") or {}
                    ce_market = ce.get("market_data") or {}
                    ce_greeks = ce.get("option_greeks") or {}
                    
                    ce_oi = int(ce_market.get("oi", 0))
                    ce_prev_oi = int(ce_market.get("prev_oi", 0))
                    
                    # Put Option Details
                    pe = row.get("put_options") or {}
                    pe_market = pe.get("market_data") or {}
                    pe_greeks = pe.get("option_greeks") or {}
                    
                    pe_oi = int(pe_market.get("oi", 0))
                    pe_prev_oi = int(pe_market.get("prev_oi", 0))

                    parsed_strikes.append({
                        "strike": strike,
                        "call_oi": ce_oi,
                        "call_change_oi": ce_oi - ce_prev_oi,
                        "call_volume": int(ce_market.get("volume", 0)),
                        "call_iv": float(ce_greeks.get("iv", 0.0)),
                        "call_ltp": float(ce_market.get("ltp", 0.0)),
                        "call_bid": float(ce_market.get("bid_price", 0.0)),
                        "call_ask": float(ce_market.get("ask_price", 0.0)),
                        "call_delta": float(ce_greeks.get("delta", 0.0)),
                        "call_gamma": float(ce_greeks.get("gamma", 0.0)),
                        "call_theta": float(ce_greeks.get("theta", 0.0)),
                        "call_vega": float(ce_greeks.get("vega", 0.0)),
                        
                        "put_oi": pe_oi,
                        "put_change_oi": pe_oi - pe_prev_oi,
                        "put_volume": int(pe_market.get("volume", 0)),
                        "put_iv": float(pe_greeks.get("iv", 0.0)),
                        "put_ltp": float(pe_market.get("ltp", 0.0)),
                        "put_bid": float(pe_market.get("bid_price", 0.0)),
                        "put_ask": float(pe_market.get("ask_price", 0.0)),
                        "put_delta": float(pe_greeks.get("delta", 0.0)),
                        "put_gamma": float(pe_greeks.get("gamma", 0.0)),
                        "put_theta": float(pe_greeks.get("theta", 0.0)),
                        "put_vega": float(pe_greeks.get("vega", 0.0))
                    })
                    
                formatted_expiry = self._format_expiry_date(expiry)
                formatted_expiry_list = [self._format_expiry_date(exp) for exp in unique_expiries]
                
                results.append({
                    "symbol": symbol,
                    "spot_price": spot_price,
                    "expiry_date": formatted_expiry,
                    "expiry_dates": formatted_expiry_list,
                    "strikes": parsed_strikes,
                    "raw_payload": json.dumps(chain_payload)
                })

            return results
