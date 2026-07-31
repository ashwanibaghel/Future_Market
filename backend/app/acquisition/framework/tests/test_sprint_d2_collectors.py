import os
import tempfile
import pyarrow as pa
import pyarrow.parquet as pq

from app.acquisition.collectors.nifty50_collector import Nifty50EquityCollector
from app.acquisition.collectors.sector_collector import SectorIndexCollector
from app.acquisition.collectors.vix_collector import IndiaVixCollector
from app.acquisition.framework.storage_registry import StorageRegistry
from app.acquisition.framework.backfill_framework import HistoricalBackfillFramework
from app.research_os.governance.dataset_registry import DatasetRegistry


def test_sprint_d2_collectors_and_backfill():
    with tempfile.TemporaryDirectory() as tmpdir:
        lake_dir = os.path.join(tmpdir, "parquet_lake")
        archive_dir = os.path.join(tmpdir, "raw_archive")

        storage = StorageRegistry(base_lake_dir=lake_dir, raw_archive_dir=archive_dir)
        dataset_reg = DatasetRegistry()

        # 1. NIFTY 50 Collector Backfill Test
        nifty_collector = Nifty50EquityCollector()
        nifty_fw = HistoricalBackfillFramework(collector=nifty_collector, storage_registry=storage, dataset_registry=dataset_reg)
        m_nifty = nifty_fw.run_backfill_chunk(exchange="NSE_EQ", symbol="RELIANCE", year="2021", month="03", start_date="2021-03-01", end_date="2021-03-31")

        assert m_nifty is not None
        assert m_nifty.asset_type == "EQUITIES"
        assert m_nifty.symbols == ["RELIANCE"]
        assert m_nifty.row_count == 2
        p_nifty = storage.get_canonical_partition_path("NSE_EQ", "RELIANCE", "2021", "03", "EQUITIES")
        assert os.path.exists(p_nifty)

        # 2. Sector Index Collector Backfill Test
        sector_collector = SectorIndexCollector()
        sector_fw = HistoricalBackfillFramework(collector=sector_collector, storage_registry=storage, dataset_registry=dataset_reg)
        m_sector = sector_fw.run_backfill_chunk(exchange="NSE_INDICES", symbol="NIFTY_BANK", year="2021", month="03", start_date="2021-03-01", end_date="2021-03-31")

        assert m_sector is not None
        assert m_sector.asset_type == "INDICES"
        assert m_sector.symbols == ["NIFTY_BANK"]

        # 3. India VIX Collector Backfill Test
        vix_collector = IndiaVixCollector()
        vix_fw = HistoricalBackfillFramework(collector=vix_collector, storage_registry=storage, dataset_registry=dataset_reg)
        m_vix = vix_fw.run_backfill_chunk(exchange="NSE_INDICES", symbol="INDIA_VIX", year="2021", month="03", start_date="2021-03-01", end_date="2021-03-31")

        assert m_vix is not None
        assert m_vix.asset_type == "VIX"
        assert m_vix.row_count == 2


if __name__ == "__main__":
    test_sprint_d2_collectors_and_backfill()
    print("\nALL SPRINT D2 COLLECTOR UNIT TESTS PASSED SUCCESSFULLY!")
