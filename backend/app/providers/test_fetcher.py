import asyncio
import logging
from datetime import datetime
from app.providers.nse_provider import NSEProvider
from app.db.session import SessionLocal
from app.db.models import OptionChainSnapshot, OptionChainStrike, RawProviderResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fetch_and_save(provider, symbol: str):
    logger.info(f"Running fetch and save for {symbol}...")
    try:
        result = await provider.fetch_option_chain(symbol)
        
        logger.info(f"--- Standardized Response Details for {symbol} ---")
        logger.info(f"Symbol: {result['symbol']}")
        logger.info(f"Spot Price: {result['spot_price']}")
        logger.info(f"Nearest Expiry Date: {result['expiry_date']}")
        logger.info(f"Number of Strikes Extracted: {len(result['strikes'])}")
        
        db = SessionLocal()
        try:
            # 1. Save Raw Payload
            raw_response = RawProviderResponse(
                timestamp=datetime.utcnow(),
                provider="NSE",
                symbol=result['symbol'],
                payload_json=result['raw_payload']
            )
            db.add(raw_response)
            db.commit()
            
            # 2. Save Option Chain Snapshot
            start_time = datetime.utcnow()
            snapshot = OptionChainSnapshot(
                timestamp=datetime.utcnow(),
                symbol=result['symbol'],
                instrument_type="INDEX",
                expiry_date=result['expiry_date'],
                spot_price=result['spot_price'],
                provider="NSE",
                collection_status="SUCCESS",
                collection_duration_ms=0
            )
            db.add(snapshot)
            db.commit()
            db.refresh(snapshot)
            
            # Update duration
            duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            snapshot.collection_duration_ms = duration
            db.commit()
            
            # 3. Save Strikes
            strikes_to_save = []
            for item in result['strikes']:
                strike_record = OptionChainStrike(
                    snapshot_id=snapshot.id,
                    strike=item['strike'],
                    call_oi=item['call_oi'],
                    call_change_oi=item['call_change_oi'],
                    call_volume=item['call_volume'],
                    call_iv=item['call_iv'],
                    call_ltp=item['call_ltp'],
                    call_bid=item['call_bid'],
                    call_ask=item['call_ask'],
                    put_oi=item['put_oi'],
                    put_change_oi=item['put_change_oi'],
                    put_volume=item['put_volume'],
                    put_iv=item['put_iv'],
                    put_ltp=item['put_ltp'],
                    put_bid=item['put_bid'],
                    put_ask=item['put_ask']
                )
                strikes_to_save.append(strike_record)
            
            db.bulk_save_objects(strikes_to_save)
            db.commit()
            logger.info(f"Successfully saved {len(strikes_to_save)} strikes for {symbol} to database!")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to fetch/save {symbol}: {str(e)}")

async def main():
    provider = NSEProvider()
    # Fetch NIFTY
    await fetch_and_save(provider, "NIFTY")
    # Wait a bit between calls to be gentle to NSE
    await asyncio.sleep(2)
    # Fetch BANKNIFTY
    await fetch_and_save(provider, "BANKNIFTY")

if __name__ == "__main__":
    asyncio.run(main())
