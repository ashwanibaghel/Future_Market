import httpx
import json
import logging
from typing import Dict, Any, List
from datetime import datetime
from app.providers.base import BaseProvider

logger = logging.getLogger(__name__)

class NSEProvider(BaseProvider):
    def __init__(self):
        self.base_url = "https://www.nseindia.com"
        self.headers = {
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0',
            'DNT': '1',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Sec-Fetch-User': '?1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-Mode': 'navigate',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'en-US,en;q=0.9,hi;q=0.8',
        }
        self.cookies = {}

    async def _init_session(self, client: httpx.AsyncClient):
        """
        Hits the main NSE option chain landing page to collect cookies.
        """
        try:
            logger.info("Initializing NSE session cookies from /option-chain...")
            # Hitting the option-chain page directly as it is less protected than home page
            response = await client.get(
                f"{self.base_url}/option-chain",
                headers=self.headers,
                timeout=10.0
            )
            self.cookies = dict(response.cookies)
            logger.info(f"Session cookies set successfully: {list(self.cookies.keys())}")
        except Exception as e:
            logger.error(f"Failed to initialize NSE session: {str(e)}")
            raise e

    async def fetch_option_chain(self, symbol: str) -> Dict[str, Any]:
        """
        Fetches option chain derivatives data from the working NextApi endpoint.
        """
        api_url = f"{self.base_url}/api/NextApi/apiClient/GetQuoteApi?functionName=getSymbolDerivativesData&symbol={symbol}"
        
        async with httpx.AsyncClient(follow_redirects=True) as client:
            # Step 1: Initialize cookies if they aren't set
            if not self.cookies:
                await self._init_session(client)
            
            # Step 2: Fetch data
            try:
                logger.info(f"Fetching option chain (NextApi) for {symbol}...")
                response = await client.get(
                    api_url,
                    headers=self.headers,
                    cookies=self.cookies,
                    timeout=10.0
                )
                
                # If unauthorized, try re-initializing session cookies once
                if response.status_code in [401, 403]:
                    logger.warning("Session expired or unauthorized. Re-initializing session...")
                    await self._init_session(client)
                    response = await client.get(
                        api_url,
                        headers=self.headers,
                        cookies=self.cookies,
                        timeout=10.0
                    )
                
                response.raise_for_status()
                data = response.json()
                
                return self._parse_nse_derivatives_response(symbol, data)
                
            except Exception as e:
                logger.error(f"Failed to fetch option chain from NSE for {symbol}: {str(e)}")
                raise e

    def _parse_nse_derivatives_response(self, symbol: str, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parses NextApi derivatives quote payload into standardized format for top N expiries.
        """
        records = data.get("data", [])
        if not records:
            raise ValueError(f"No records found in NextApi response for {symbol}")
            
        # Filter for Options (OPTIDX) only
        options = [r for r in records if r.get("instrumentType") == "OPTIDX"]
        if not options:
            raise ValueError(f"No option contracts (OPTIDX) found in derivatives data for {symbol}")
            
        # Extract spot price (underlyingValue is present in each record)
        spot_price = 0.0
        for opt in options:
            val = opt.get("underlyingValue")
            if val:
                spot_price = float(val)
                break
                
        # Extract unique expiry dates and sort them
        # Expiry date format: '23-Jun-2026'
        unique_expiries = list(set(opt.get("expiryDate") for opt in options if opt.get("expiryDate")))
        
        def parse_date(date_str):
            try:
                return datetime.strptime(date_str, "%d-%b-%Y")
            except Exception:
                return datetime.max
                
        unique_expiries.sort(key=parse_date)
        
        if not unique_expiries:
            raise ValueError(f"No expiry dates found in option contracts for {symbol}")
            
        # Select top N expiries
        from app.config import settings
        tracked_expiries = unique_expiries[:settings.TRACK_EXPIRIES_COUNT]
        
        results = []
        raw_payload_str = json.dumps(data)
        
        for expiry in tracked_expiries:
            # Filter options for the specific expiry date
            expiry_options = [opt for opt in options if opt.get("expiryDate") == expiry]
            
            # Group by strike price
            strikes_map = {}
            for opt in expiry_options:
                strike_str = opt.get("strikePrice", "").strip()
                if not strike_str:
                    continue
                try:
                    strike = float(strike_str)
                except ValueError:
                    continue
                    
                if strike not in strikes_map:
                    strikes_map[strike] = {"CE": None, "PE": None}
                    
                opt_type = opt.get("optionType") # "CE" or "PE"
                if opt_type in ["CE", "PE"]:
                    strikes_map[strike][opt_type] = opt
                    
            # Build standardized strikes list
            parsed_strikes = []
            for strike, contracts in strikes_map.items():
                ce = contracts["CE"] or {}
                pe = contracts["PE"] or {}
                
                parsed_strikes.append({
                    "strike": strike,
                    "call_oi": int(ce.get("openInterest", 0)),
                    "call_change_oi": int(ce.get("changeinOpenInterest", 0)),
                    "call_volume": int(ce.get("totalTradedVolume", 0)),
                    "call_iv": 0.0, # Will be calculated in analytics engine
                    "call_ltp": float(ce.get("lastPrice", 0.0)),
                    "call_bid": 0.0,
                    "call_ask": 0.0,
                    "put_oi": int(pe.get("openInterest", 0)),
                    "put_change_oi": int(pe.get("changeinOpenInterest", 0)),
                    "put_volume": int(pe.get("totalTradedVolume", 0)),
                    "put_iv": 0.0, # Will be calculated in analytics engine
                    "put_ltp": float(pe.get("lastPrice", 0.0)),
                    "put_bid": 0.0,
                    "put_ask": 0.0
                })
                
            results.append({
                "symbol": symbol,
                "spot_price": spot_price,
                "expiry_date": expiry,
                "expiry_dates": unique_expiries,
                "strikes": parsed_strikes,
                "raw_payload": raw_payload_str
            })
            
        return results
